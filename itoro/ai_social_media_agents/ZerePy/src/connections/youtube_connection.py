import os
import json
import logging
import pickle
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import print_h_bar

logger = logging.getLogger("connections.youtube_connection")

class YouTubeConnectionError(Exception):
    """Base exception for YouTube connection errors"""
    pass

class YouTubeConfigurationError(YouTubeConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class YouTubeAPIError(YouTubeConnectionError):
    """Raised when YouTube API requests fail"""
    pass

class YouTubeConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.youtube = None
        self.credentials = None

        # YouTube Data API v3 scopes
        self._scopes = [
            'https://www.googleapis.com/auth/youtube',
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube.force-ssl',
            'https://www.googleapis.com/auth/youtubepartner',
            'https://www.googleapis.com/auth/youtube.readonly'
        ]

        # API quota management (10,000 units per day)
        self._daily_quota_used = 0
        self._quota_reset_date = datetime.now().date()

        # Cache for channel info
        self._channel_info = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate YouTube configuration from JSON"""
        required_fields = []
        # Channel ID is optional for initial setup, can be discovered later

        # Optional fields with defaults
        config.setdefault("auto_upload_enabled", False)
        config.setdefault("comment_moderation", "manual")  # manual, auto, disabled
        config.setdefault("analytics_reporting", True)
        config.setdefault("live_stream_management", False)
        config.setdefault("monetization_management", False)
        config.setdefault("bulk_operations", True)

        return config

    def _get_credentials(self) -> Credentials:
        """Handle OAuth 2.0 authentication with automatic token refresh"""
        logger.debug("Retrieving YouTube credentials")

        creds = None
        token_path = Path.home() / '.zerepy' / 'youtube_token.pickle'

        # Ensure config directory exists
        token_path.parent.mkdir(exist_ok=True)

        # Load existing credentials
        if token_path.exists():
            try:
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                logger.warning(f"Failed to load existing token: {e}")

        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.debug("Refreshing expired credentials")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Failed to refresh token: {e}")
                    creds = None

            if not creds:
                logger.info("No valid credentials found, starting OAuth flow")
                creds = self._run_oauth_flow()

            # Save credentials
            try:
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
                logger.debug("Credentials saved successfully")
            except Exception as e:
                logger.error(f"Failed to save credentials: {e}")

        return creds

    def _run_oauth_flow(self) -> Credentials:
        """Run the OAuth 2.0 flow to get user consent"""
        try:
            # Get client secrets from environment
            client_id = os.getenv('YOUTUBE_CLIENT_ID')
            client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')

            if not client_id or not client_secret:
                raise YouTubeConfigurationError(
                    "YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in environment variables"
                )

            # Create client secrets dict
            client_secrets = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }

            # Create flow
            flow = InstalledAppFlow.from_client_config(client_secrets, self._scopes)

            # Run local server flow
            creds = flow.run_local_server(port=8080, prompt='consent')

            return creds

        except Exception as e:
            raise YouTubeConfigurationError(f"OAuth flow failed: {str(e)}")

    def _init_youtube_service(self):
        """Initialize the YouTube API service"""
        if not self.youtube:
            if not self.credentials:
                self.credentials = self._get_credentials()

            try:
                self.youtube = build('youtube', 'v3', credentials=self.credentials)
                logger.debug("YouTube API service initialized successfully")
            except Exception as e:
                raise YouTubeAPIError(f"Failed to initialize YouTube service: {str(e)}")

    def _check_quota(self, cost: int = 1) -> bool:
        """Check if we have quota remaining for the operation"""
        today = datetime.now().date()

        # Reset quota counter if it's a new day
        if today != self._quota_reset_date:
            self._daily_quota_used = 0
            self._quota_reset_date = today

        # Check if operation would exceed quota
        if self._daily_quota_used + cost > 10000:  # 10,000 units per day
            logger.warning(f"Daily quota limit approaching: {self._daily_quota_used}/{10000}")
            return False

        self._daily_quota_used += cost
        return True

    def _get_channel_info(self) -> Dict[str, Any]:
        """Get authenticated user's channel information"""
        if self._channel_info:
            return self._channel_info

        try:
            self._init_youtube_service()

            request = self.youtube.channels().list(
                part='snippet,statistics,status,contentDetails',
                mine=True
            )

            response = request.execute()
            self._check_quota(3)  # channels.list costs 3 units

            if response['items']:
                self._channel_info = response['items'][0]
                return self._channel_info
            else:
                raise YouTubeAPIError("No channel found for authenticated user")

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to get channel info: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Channel info retrieval failed: {str(e)}")

    def configure(self) -> bool:
        """Set up YouTube API authentication"""
        logger.info("Starting YouTube API authentication setup")

        try:
            # Check if already configured
            if self.is_configured(verbose=False):
                logger.info("YouTube API is already configured")
                response = input("Do you want to reconfigure? (y/n): ")
                if response.lower() != 'y':
                    return True

            setup_instructions = [
                "\n📺 YOUTUBE API AUTHENTICATION SETUP",
                "\n📝 To get your YouTube API credentials:",
                "1. Go to https://console.developers.google.com/",
                "2. Create a new project or select existing one",
                "3. Enable the YouTube Data API v3",
                "4. Create OAuth 2.0 credentials (Desktop application)",
                "5. Download the client secrets JSON file",
                "6. Set environment variables:"
            ]
            logger.info("\n".join(setup_instructions))

            env_instructions = [
                "YOUTUBE_CLIENT_ID=your_client_id",
                "YOUTUBE_CLIENT_SECRET=your_client_secret"
            ]
            logger.info("\nRequired environment variables:")
            for env_var in env_instructions:
                logger.info(f"  {env_var}")
            print_h_bar()

            # Check environment variables
            client_id = os.getenv('YOUTUBE_CLIENT_ID')
            client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')

            if not client_id or not client_secret:
                logger.error("Missing required environment variables")
                logger.info("Please set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET")
                return False

            logger.info("Environment variables found ✓")
            logger.info("Starting OAuth authentication flow...")

            # Run authentication flow
            self.credentials = self._run_oauth_flow()
            self._init_youtube_service()

            # Test connection by getting channel info
            channel_info = self._get_channel_info()
            channel_title = channel_info['snippet']['title']

            logger.info(f"✅ Successfully authenticated with YouTube!")
            logger.info(f"Channel: {channel_title}")
            logger.info("YouTube API is now configured and ready to use.")
            return True

        except Exception as e:
            error_msg = f"Setup failed: {str(e)}"
            logger.error(error_msg)
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if YouTube API credentials are configured and valid"""
        logger.debug("Checking YouTube configuration status")
        try:
            # Check environment variables
            client_id = os.getenv('YOUTUBE_CLIENT_ID')
            client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')

            if not client_id or not client_secret:
                if verbose:
                    logger.error("Missing environment variables: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET")
                return False

            # Try to initialize service
            self._init_youtube_service()

            # Test by getting channel info
            self._get_channel_info()

            logger.debug("YouTube configuration is valid")
            return True

        except Exception as e:
            if verbose:
                error_msg = str(e)
                if isinstance(e, YouTubeConfigurationError):
                    error_msg = f"Configuration error: {error_msg}"
                elif isinstance(e, YouTubeAPIError):
                    error_msg = f"API validation error: {error_msg}"
                logger.error(f"Configuration validation failed: {error_msg}")
            return False

    def register_actions(self) -> None:
        """Register available YouTube actions"""
        self.actions = {
            # Video Management
            "upload_video": Action(
                name="upload_video",
                parameters=[
                    ActionParameter("file_path", True, str, "Path to the video file to upload"),
                    ActionParameter("title", True, str, "Video title"),
                    ActionParameter("description", False, str, "Video description"),
                    ActionParameter("tags", False, list, "List of tags for the video"),
                    ActionParameter("privacy_status", False, str, "Privacy status: public, private, unlisted"),
                    ActionParameter("thumbnail_path", False, str, "Path to thumbnail image"),
                    ActionParameter("publish_at", False, str, "Scheduled publish time (ISO 8601 format)"),
                    ActionParameter("playlist_ids", False, list, "List of playlist IDs to add video to"),
                ],
                description="Upload a video to YouTube with full metadata and scheduling options"
            ),
            "update_video": Action(
                name="update_video",
                parameters=[
                    ActionParameter("video_id", True, str, "ID of the video to update"),
                    ActionParameter("title", False, str, "New video title"),
                    ActionParameter("description", False, str, "New video description"),
                    ActionParameter("tags", False, list, "New list of tags"),
                    ActionParameter("privacy_status", False, str, "New privacy status"),
                    ActionParameter("thumbnail_path", False, str, "Path to new thumbnail"),
                ],
                description="Update video metadata, privacy settings, or thumbnail"
            ),
            "delete_video": Action(
                name="delete_video",
                parameters=[
                    ActionParameter("video_id", True, str, "ID of the video to delete"),
                ],
                description="Delete a video from the channel"
            ),
            "get_video_details": Action(
                name="get_video_details",
                parameters=[
                    ActionParameter("video_id", True, str, "ID of the video to get details for"),
                ],
                description="Get comprehensive video information including statistics"
            ),

            # Playlist Management
            "create_playlist": Action(
                name="create_playlist",
                parameters=[
                    ActionParameter("title", True, str, "Playlist title"),
                    ActionParameter("description", False, str, "Playlist description"),
                    ActionParameter("privacy_status", False, str, "Privacy status: public, private, unlisted"),
                    ActionParameter("tags", False, list, "List of tags for the playlist"),
                ],
                description="Create a new YouTube playlist"
            ),
            "add_to_playlist": Action(
                name="add_to_playlist",
                parameters=[
                    ActionParameter("playlist_id", True, str, "ID of the playlist"),
                    ActionParameter("video_id", True, str, "ID of the video to add"),
                    ActionParameter("position", False, int, "Position in playlist (0-based)"),
                ],
                description="Add a video to an existing playlist"
            ),
            "remove_from_playlist": Action(
                name="remove_from_playlist",
                parameters=[
                    ActionParameter("playlist_id", True, str, "ID of the playlist"),
                    ActionParameter("video_id", True, str, "ID of the video to remove"),
                ],
                description="Remove a video from a playlist"
            ),

            # Comment Management
            "get_video_comments": Action(
                name="get_video_comments",
                parameters=[
                    ActionParameter("video_id", True, str, "ID of the video to get comments for"),
                    ActionParameter("max_results", False, int, "Maximum number of comments to retrieve (default: 100)"),
                    ActionParameter("order", False, str, "Comment order: relevance, time"),
                ],
                description="Retrieve comments from a video"
            ),
            "reply_to_comment": Action(
                name="reply_to_comment",
                parameters=[
                    ActionParameter("comment_id", True, str, "ID of the comment to reply to"),
                    ActionParameter("text", True, str, "Reply text content"),
                ],
                description="Reply to a comment on a video"
            ),
            "moderate_comment": Action(
                name="moderate_comment",
                parameters=[
                    ActionParameter("comment_id", True, str, "ID of the comment to moderate"),
                    ActionParameter("action", True, str, "Action: approve, reject, delete, mark_spam"),
                ],
                description="Moderate a comment (approve, reject, delete, or mark as spam)"
            ),

            # Analytics & Reporting
            "get_channel_analytics": Action(
                name="get_channel_analytics",
                parameters=[
                    ActionParameter("start_date", False, str, "Start date (YYYY-MM-DD, default: 30 days ago)"),
                    ActionParameter("end_date", False, str, "End date (YYYY-MM-DD, default: today)"),
                    ActionParameter("metrics", False, list, "Specific metrics to retrieve"),
                ],
                description="Get comprehensive channel analytics and performance data"
            ),
            "get_video_analytics": Action(
                name="get_video_analytics",
                parameters=[
                    ActionParameter("video_id", True, str, "ID of the video to analyze"),
                    ActionParameter("start_date", False, str, "Start date (YYYY-MM-DD)"),
                    ActionParameter("end_date", False, str, "End date (YYYY-MM-DD)"),
                ],
                description="Get detailed analytics for a specific video"
            ),

            # Channel Management
            "get_channel_info": Action(
                name="get_channel_info",
                parameters=[],
                description="Get comprehensive information about the authenticated channel"
            ),
            "update_channel_branding": Action(
                name="update_channel_branding",
                parameters=[
                    ActionParameter("title", False, str, "New channel title"),
                    ActionParameter("description", False, str, "New channel description"),
                    ActionParameter("keywords", False, list, "Channel keywords/tags"),
                    ActionParameter("banner_path", False, str, "Path to new banner image"),
                ],
                description="Update channel branding, description, and banner"
            ),

            # Live Streaming
            "create_live_stream": Action(
                name="create_live_stream",
                parameters=[
                    ActionParameter("title", True, str, "Stream title"),
                    ActionParameter("description", False, str, "Stream description"),
                    ActionParameter("start_time", True, str, "Scheduled start time (ISO 8601)"),
                    ActionParameter("privacy_status", False, str, "Privacy status: public, private, unlisted"),
                ],
                description="Create and schedule a live stream"
            ),
            "get_live_chat_messages": Action(
                name="get_live_chat_messages",
                parameters=[
                    ActionParameter("live_chat_id", True, str, "ID of the live chat"),
                    ActionParameter("max_results", False, int, "Maximum messages to retrieve"),
                ],
                description="Get messages from a live stream chat"
            ),

            # Community & Engagement
            "create_community_post": Action(
                name="create_community_post",
                parameters=[
                    ActionParameter("text", True, str, "Post text content"),
                    ActionParameter("image_path", False, str, "Path to image attachment"),
                ],
                description="Create a post in the community tab"
            ),

            # Bulk Operations
            "bulk_update_videos": Action(
                name="bulk_update_videos",
                parameters=[
                    ActionParameter("video_ids", True, list, "List of video IDs to update"),
                    ActionParameter("updates", True, dict, "Update operations to apply"),
                ],
                description="Apply updates to multiple videos at once"
            ),
        }

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a YouTube action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Check quota before proceeding
        if not self._check_quota():
            raise YouTubeAPIError("Daily API quota exceeded")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)

    # Video Management Actions
    def upload_video(self, file_path: str, title: str, description: str = "",
                    tags: List[str] = None, privacy_status: str = "private",
                    thumbnail_path: str = None, publish_at: str = None,
                    playlist_ids: List[str] = None, **kwargs) -> Dict[str, Any]:
        """Upload a video to YouTube with full metadata"""
        try:
            self._init_youtube_service()

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Video file not found: {file_path}")

            # Validate privacy status
            if privacy_status not in ['public', 'private', 'unlisted']:
                raise ValueError("privacy_status must be 'public', 'private', or 'unlisted'")

            # Prepare video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': '22'  # People & Blogs category by default
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }

            # Add scheduled publishing if provided
            if publish_at:
                body['status']['publishAt'] = publish_at

            # Create media upload
            media = MediaFileUpload(
                file_path,
                mimetype='video/*',
                resumable=True
            )

            # Upload video
            request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )

            response = request.execute()
            self._check_quota(1600)  # videos.insert costs 1600 units

            video_id = response['id']
            logger.info(f"Video uploaded successfully: {video_id}")

            # Upload thumbnail if provided
            if thumbnail_path and os.path.exists(thumbnail_path):
                self._upload_thumbnail(video_id, thumbnail_path)

            # Add to playlists if specified
            if playlist_ids:
                for playlist_id in playlist_ids:
                    try:
                        self._add_video_to_playlist(playlist_id, video_id)
                    except Exception as e:
                        logger.warning(f"Failed to add video to playlist {playlist_id}: {e}")

            return {
                "video_id": video_id,
                "title": title,
                "privacy_status": privacy_status,
                "upload_status": "completed",
                "url": f"https://www.youtube.com/watch?v={video_id}"
            }

        except HttpError as e:
            error_details = json.loads(e.content.decode('utf-8'))
            raise YouTubeAPIError(f"Video upload failed: {error_details.get('error', {}).get('message', str(e))}")
        except Exception as e:
            raise YouTubeAPIError(f"Video upload failed: {str(e)}")

    def update_video(self, video_id: str, title: str = None, description: str = None,
                    tags: List[str] = None, privacy_status: str = None,
                    thumbnail_path: str = None, **kwargs) -> Dict[str, Any]:
        """Update video metadata"""
        try:
            self._init_youtube_service()

            # Get current video details
            request = self.youtube.videos().list(
                part='snippet,status',
                id=video_id
            )
            response = request.execute()
            self._check_quota(3)  # videos.list costs 3 units

            if not response['items']:
                raise YouTubeAPIError(f"Video {video_id} not found")

            video = response['items'][0]
            body = {}

            # Update snippet if needed
            if any([title, description, tags]):
                body['snippet'] = video.get('snippet', {})
                if title:
                    body['snippet']['title'] = title
                if description:
                    body['snippet']['description'] = description
                if tags is not None:
                    body['snippet']['tags'] = tags

            # Update status if needed
            if privacy_status:
                if privacy_status not in ['public', 'private', 'unlisted']:
                    raise ValueError("privacy_status must be 'public', 'private', or 'unlisted'")
                body['status'] = {'privacyStatus': privacy_status}

            if not body:
                raise ValueError("No updates specified")

            # Update video
            request = self.youtube.videos().update(
                part=','.join(body.keys()),
                body=body
            )

            response = request.execute()
            self._check_quota(50)  # videos.update costs 50 units

            # Upload thumbnail if provided
            if thumbnail_path and os.path.exists(thumbnail_path):
                self._upload_thumbnail(video_id, thumbnail_path)

            return {
                "video_id": video_id,
                "updated_fields": list(body.keys()),
                "update_status": "completed"
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Video update failed: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Video update failed: {str(e)}")

    def delete_video(self, video_id: str, **kwargs) -> Dict[str, Any]:
        """Delete a video from the channel"""
        try:
            self._init_youtube_service()

            request = self.youtube.videos().delete(id=video_id)
            request.execute()
            self._check_quota(50)  # videos.delete costs 50 units

            return {
                "video_id": video_id,
                "delete_status": "completed"
            }

        except HttpError as e:
            if e.resp.status == 404:
                raise YouTubeAPIError(f"Video {video_id} not found")
            raise YouTubeAPIError(f"Video deletion failed: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Video deletion failed: {str(e)}")

    def get_video_details(self, video_id: str, **kwargs) -> Dict[str, Any]:
        """Get comprehensive video information"""
        try:
            self._init_youtube_service()

            request = self.youtube.videos().list(
                part='snippet,statistics,status,contentDetails,liveStreamingDetails',
                id=video_id
            )

            response = request.execute()
            self._check_quota(3)  # videos.list costs 3 units

            if not response['items']:
                raise YouTubeAPIError(f"Video {video_id} not found")

            video = response['items'][0]

            return {
                "video_id": video_id,
                "title": video['snippet']['title'],
                "description": video['snippet']['description'],
                "channel_title": video['snippet']['channelTitle'],
                "published_at": video['snippet']['publishedAt'],
                "tags": video['snippet'].get('tags', []),
                "privacy_status": video['status']['privacyStatus'],
                "view_count": int(video['statistics'].get('viewCount', 0)),
                "like_count": int(video['statistics'].get('likeCount', 0)),
                "comment_count": int(video['statistics'].get('commentCount', 0)),
                "duration": video['contentDetails']['duration'],
                "thumbnail_url": video['snippet']['thumbnails'].get('high', {}).get('url', ''),
                "url": f"https://www.youtube.com/watch?v={video_id}"
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to get video details: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to get video details: {str(e)}")

    # Playlist Management Actions
    def create_playlist(self, title: str, description: str = "",
                       privacy_status: str = "private", tags: List[str] = None,
                       **kwargs) -> Dict[str, Any]:
        """Create a new YouTube playlist"""
        try:
            self._init_youtube_service()

            if privacy_status not in ['public', 'private', 'unlisted']:
                raise ValueError("privacy_status must be 'public', 'private', or 'unlisted'")

            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or []
                },
                'status': {
                    'privacyStatus': privacy_status
                }
            }

            request = self.youtube.playlists().insert(
                part='snippet,status',
                body=body
            )

            response = request.execute()
            self._check_quota(50)  # playlists.insert costs 50 units

            return {
                "playlist_id": response['id'],
                "title": title,
                "privacy_status": privacy_status,
                "url": f"https://www.youtube.com/playlist?list={response['id']}"
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Playlist creation failed: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Playlist creation failed: {str(e)}")

    def add_to_playlist(self, playlist_id: str, video_id: str, position: int = None,
                       **kwargs) -> Dict[str, Any]:
        """Add a video to a playlist"""
        try:
            self._init_youtube_service()

            body = {
                'snippet': {
                    'playlistId': playlist_id,
                    'resourceId': {
                        'kind': 'youtube#video',
                        'videoId': video_id
                    }
                }
            }

            if position is not None:
                body['snippet']['position'] = position

            request = self.youtube.playlistItems().insert(
                part='snippet',
                body=body
            )

            response = request.execute()
            self._check_quota(50)  # playlistItems.insert costs 50 units

            return {
                "playlist_item_id": response['id'],
                "playlist_id": playlist_id,
                "video_id": video_id,
                "position": position
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to add video to playlist: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to add video to playlist: {str(e)}")

    def remove_from_playlist(self, playlist_id: str, video_id: str, **kwargs) -> Dict[str, Any]:
        """Remove a video from a playlist"""
        try:
            self._init_youtube_service()

            # First find the playlist item ID
            request = self.youtube.playlistItems().list(
                part='id',
                playlistId=playlist_id,
                videoId=video_id,
                maxResults=1
            )

            response = request.execute()
            self._check_quota(3)  # playlistItems.list costs 3 units

            if not response['items']:
                raise YouTubeAPIError(f"Video {video_id} not found in playlist {playlist_id}")

            item_id = response['items'][0]['id']

            # Delete the playlist item
            request = self.youtube.playlistItems().delete(id=item_id)
            request.execute()
            self._check_quota(50)  # playlistItems.delete costs 50 units

            return {
                "playlist_id": playlist_id,
                "video_id": video_id,
                "removal_status": "completed"
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to remove video from playlist: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to remove video from playlist: {str(e)}")

    # Comment Management Actions
    def get_video_comments(self, video_id: str, max_results: int = 100,
                          order: str = "relevance", **kwargs) -> List[Dict[str, Any]]:
        """Get comments from a video"""
        try:
            self._init_youtube_service()

            if max_results > 100:
                max_results = 100
            if order not in ['relevance', 'time']:
                order = 'relevance'

            request = self.youtube.commentThreads().list(
                part='snippet,replies',
                videoId=video_id,
                maxResults=max_results,
                order=order
            )

            response = request.execute()
            self._check_quota(3)  # commentThreads.list costs 3 units

            comments = []
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    "comment_id": item['id'],
                    "video_id": video_id,
                    "author": comment['authorDisplayName'],
                    "author_channel_id": comment['authorChannelId']['value'],
                    "text": comment['textDisplay'],
                    "like_count": comment['likeCount'],
                    "published_at": comment['publishedAt'],
                    "updated_at": comment['updatedAt'],
                    "reply_count": item['snippet']['totalReplyCount']
                })

            return comments

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to get video comments: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to get video comments: {str(e)}")

    def reply_to_comment(self, comment_id: str, text: str, **kwargs) -> Dict[str, Any]:
        """Reply to a comment"""
        try:
            self._init_youtube_service()

            body = {
                'snippet': {
                    'parentId': comment_id,
                    'textOriginal': text
                }
            }

            request = self.youtube.comments().insert(
                part='snippet',
                body=body
            )

            response = request.execute()
            self._check_quota(50)  # comments.insert costs 50 units

            return {
                "reply_id": response['id'],
                "parent_comment_id": comment_id,
                "text": text,
                "reply_status": "posted"
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to reply to comment: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to reply to comment: {str(e)}")

    def moderate_comment(self, comment_id: str, action: str, **kwargs) -> Dict[str, Any]:
        """Moderate a comment"""
        try:
            self._init_youtube_service()

            if action not in ['approve', 'reject', 'delete', 'mark_spam']:
                raise ValueError("Action must be: approve, reject, delete, or mark_spam")

            # For now, we can only delete comments via API
            # Other moderation actions require YouTube Studio
            if action == 'delete':
                request = self.youtube.comments().delete(id=comment_id)
                request.execute()
                self._check_quota(50)  # comments.delete costs 50 units

                return {
                    "comment_id": comment_id,
                    "action": action,
                    "moderation_status": "completed"
                }
            else:
                # For other actions, we'd need YouTube Studio API or manual intervention
                logger.warning(f"Action '{action}' requires manual intervention in YouTube Studio")
                return {
                    "comment_id": comment_id,
                    "action": action,
                    "moderation_status": "manual_required",
                    "message": f"This action requires manual intervention in YouTube Studio"
                }

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to moderate comment: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to moderate comment: {str(e)}")

    # Analytics Actions
    def get_channel_analytics(self, start_date: str = None, end_date: str = None,
                             metrics: List[str] = None, **kwargs) -> Dict[str, Any]:
        """Get comprehensive channel analytics"""
        try:
            self._init_youtube_service()

            # Default to last 30 days
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            # Build analytics request
            request = self.youtube.channels().list(
                part='statistics',
                mine=True
            )

            response = request.execute()
            self._check_quota(3)  # channels.list costs 3 units

            if not response['items']:
                raise YouTubeAPIError("No channel data found")

            stats = response['items'][0]['statistics']

            # Get channel info for additional context
            channel_info = self._get_channel_info()

            return {
                "channel_id": channel_info['id'],
                "channel_title": channel_info['snippet']['title'],
                "subscriber_count": int(stats.get('subscriberCount', 0)),
                "video_count": int(stats.get('videoCount', 0)),
                "view_count": int(stats.get('viewCount', 0)),
                "analytics_period": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "last_updated": datetime.now().isoformat()
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to get channel analytics: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to get channel analytics: {str(e)}")

    def get_video_analytics(self, video_id: str, start_date: str = None,
                           end_date: str = None, **kwargs) -> Dict[str, Any]:
        """Get analytics for a specific video"""
        try:
            # First get basic video info
            video_details = self.get_video_details(video_id)

            # Add time-based analytics if available
            analytics = {
                "video_id": video_id,
                "basic_stats": video_details,
                "analytics_period": {
                    "start_date": start_date,
                    "end_date": end_date or datetime.now().strftime('%Y-%m-%d')
                }
            }

            return analytics

        except Exception as e:
            raise YouTubeAPIError(f"Failed to get video analytics: {str(e)}")

    # Channel Management Actions
    def get_channel_info(self, **kwargs) -> Dict[str, Any]:
        """Get comprehensive channel information"""
        try:
            channel_info = self._get_channel_info()

            return {
                "channel_id": channel_info['id'],
                "title": channel_info['snippet']['title'],
                "description": channel_info['snippet']['description'],
                "custom_url": channel_info['snippet'].get('customUrl', ''),
                "published_at": channel_info['snippet']['publishedAt'],
                "country": channel_info['snippet'].get('country', ''),
                "default_language": channel_info['snippet'].get('defaultLanguage', ''),
                "subscriber_count": int(channel_info['statistics'].get('subscriberCount', 0)),
                "video_count": int(channel_info['statistics'].get('videoCount', 0)),
                "view_count": int(channel_info['statistics'].get('viewCount', 0)),
                "privacy_status": channel_info['status']['privacyStatus'],
                "is_linked": channel_info['status']['isLinked'],
                "long_uploads_status": channel_info['status']['longUploadsStatus'],
                "made_for_kids": channel_info['status']['madeForKids']
            }

        except Exception as e:
            raise YouTubeAPIError(f"Failed to get channel info: {str(e)}")

    def update_channel_branding(self, title: str = None, description: str = None,
                               keywords: List[str] = None, banner_path: str = None,
                               **kwargs) -> Dict[str, Any]:
        """Update channel branding and information"""
        try:
            self._init_youtube_service()

            channel_info = self._get_channel_info()
            body = {'id': channel_info['id']}

            # Update branding
            if any([title, description, keywords]):
                body['brandingSettings'] = channel_info.get('brandingSettings', {})

                if title or description:
                    body['brandingSettings']['channel'] = body['brandingSettings'].get('channel', {})
                    if title:
                        body['brandingSettings']['channel']['title'] = title
                    if description:
                        body['brandingSettings']['channel']['description'] = description

                if keywords:
                    body['brandingSettings']['channel'] = body['brandingSettings'].get('channel', {})
                    body['brandingSettings']['channel']['keywords'] = ' '.join(keywords)

            if not body.get('brandingSettings'):
                raise ValueError("No branding updates specified")

            request = self.youtube.channels().update(
                part='brandingSettings',
                body=body
            )

            response = request.execute()
            self._check_quota(50)  # channels.update costs 50 units

            # Note: Banner upload requires additional API calls and is more complex
            if banner_path:
                logger.warning("Banner upload requires additional setup and is not implemented in this version")

            return {
                "channel_id": channel_info['id'],
                "updated_fields": list(body.keys()),
                "update_status": "completed"
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to update channel branding: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to update channel branding: {str(e)}")

    # Live Streaming Actions
    def create_live_stream(self, title: str, description: str = "",
                          start_time: str = None, privacy_status: str = "private",
                          **kwargs) -> Dict[str, Any]:
        """Create and schedule a live stream"""
        try:
            self._init_youtube_service()

            # Create broadcast
            broadcast_body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'scheduledStartTime': start_time
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }

            broadcast_request = self.youtube.liveBroadcasts().insert(
                part='snippet,status',
                body=broadcast_body
            )

            broadcast_response = broadcast_request.execute()
            self._check_quota(50)  # liveBroadcasts.insert costs 50 units

            broadcast_id = broadcast_response['id']

            # Create stream
            stream_body = {
                'snippet': {
                    'title': f"{title} - Stream"
                },
                'cdn': {
                    'format': '720p',
                    'ingestionType': 'rtmp'
                }
            }

            stream_request = self.youtube.liveStreams().insert(
                part='snippet,cdn',
                body=stream_body
            )

            stream_response = stream_request.execute()
            self._check_quota(50)  # liveStreams.insert costs 50 units

            stream_id = stream_response['id']

            # Bind broadcast to stream
            bind_request = self.youtube.liveBroadcasts().bind(
                id=broadcast_id,
                part='id',
                streamId=stream_id
            )

            bind_request.execute()
            self._check_quota(50)  # liveBroadcasts.bind costs 50 units

            return {
                "broadcast_id": broadcast_id,
                "stream_id": stream_id,
                "title": title,
                "scheduled_start_time": start_time,
                "stream_url": stream_response['cdn']['ingestionInfo']['streamName'],
                "stream_key": "HIDDEN_FOR_SECURITY",  # Never expose in logs
                "status": "scheduled"
            }

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to create live stream: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to create live stream: {str(e)}")

    def get_live_chat_messages(self, live_chat_id: str, max_results: int = 200,
                              **kwargs) -> List[Dict[str, Any]]:
        """Get messages from a live stream chat"""
        try:
            self._init_youtube_service()

            if max_results > 200:
                max_results = 200

            request = self.youtube.liveChatMessages().list(
                liveChatId=live_chat_id,
                part='snippet,authorDetails',
                maxResults=max_results
            )

            response = request.execute()
            self._check_quota(5)  # liveChatMessages.list costs 5 units

            messages = []
            for item in response['items']:
                snippet = item['snippet']
                author = item['authorDetails']

                messages.append({
                    "message_id": item['id'],
                    "live_chat_id": live_chat_id,
                    "author_name": author['displayName'],
                    "author_channel_id": author['channelId'],
                    "message_text": snippet['textMessageDetails']['messageText'] if 'textMessageDetails' in snippet else '',
                    "published_at": snippet['publishedAt'],
                    "message_type": snippet['type']
                })

            return messages

        except HttpError as e:
            raise YouTubeAPIError(f"Failed to get live chat messages: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Failed to get live chat messages: {str(e)}")

    # Community Features
    def create_community_post(self, text: str, image_path: str = None, **kwargs) -> Dict[str, Any]:
        """Create a post in the community tab"""
        try:
            self._init_youtube_service()

            channel_info = self._get_channel_info()
            channel_id = channel_info['id']

            body = {
                'snippet': {
                    'channelId': channel_id,
                    'description': text
                }
            }

            # Note: Community posts API is limited and may not support images
            # This is a basic text-only implementation
            if image_path:
                logger.warning("Image attachments for community posts are not supported in this version")

            request = self.youtube.channelSections().insert(
                part='snippet',
                body=body
            )

            # Actually, community posts use a different endpoint
            # This is a placeholder - full implementation would require
            # the YouTube Partner API or manual posting
            logger.warning("Community posts require YouTube Partner API access")

            return {
                "post_status": "not_implemented",
                "message": "Community posts require YouTube Partner API access",
                "text": text
            }

        except Exception as e:
            raise YouTubeAPIError(f"Failed to create community post: {str(e)}")

    # Bulk Operations
    def bulk_update_videos(self, video_ids: List[str], updates: Dict[str, Any],
                          **kwargs) -> Dict[str, Any]:
        """Apply updates to multiple videos at once"""
        results = []

        for video_id in video_ids:
            try:
                result = self.update_video(video_id, **updates)
                results.append({"video_id": video_id, "status": "success", "result": result})
            except Exception as e:
                results.append({"video_id": video_id, "status": "error", "error": str(e)})

        return {
            "total_videos": len(video_ids),
            "successful_updates": len([r for r in results if r["status"] == "success"]),
            "failed_updates": len([r for r in results if r["status"] == "error"]),
            "results": results
        }

    # Helper Methods
    def _upload_thumbnail(self, video_id: str, thumbnail_path: str) -> None:
        """Upload a thumbnail for a video"""
        try:
            if not os.path.exists(thumbnail_path):
                raise FileNotFoundError(f"Thumbnail file not found: {thumbnail_path}")

            request = self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype='image/*')
            )

            request.execute()
            self._check_quota(50)  # thumbnails.set costs 50 units
            logger.info(f"Thumbnail uploaded for video {video_id}")

        except Exception as e:
            logger.error(f"Failed to upload thumbnail for video {video_id}: {e}")

    def _add_video_to_playlist(self, playlist_id: str, video_id: str) -> None:
        """Helper method to add video to playlist"""
        self.add_to_playlist(playlist_id, video_id)
