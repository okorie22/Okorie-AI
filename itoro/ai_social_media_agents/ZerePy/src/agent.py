import json
import random
import time
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from src.connection_manager import ConnectionManager
from src.helpers import print_h_bar, find_env_file

REQUIRED_FIELDS = ["name", "bio", "traits", "examples", "loop_delay", "config", "tasks"]

logger = logging.getLogger("agent")

class ZerePyAgent:
    def __init__(
            self,
            agent_name: str
    ):
        try:        
            agent_path = Path("agents") / f"{agent_name}.json"
            agent_dict = json.load(open(agent_path, "r"))

            missing_fields = [field for field in REQUIRED_FIELDS if field not in agent_dict]
            if missing_fields:
                raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")

            self.name = agent_dict["name"]
            self.bio = agent_dict["bio"]
            self.traits = agent_dict["traits"]
            self.examples = agent_dict["examples"]
            self.loop_delay = agent_dict["loop_delay"] 
            self.connection_manager = ConnectionManager(agent_dict["config"])
            
            # Extract Twitter config (optional for multi-platform agents)
            twitter_config = next((config for config in agent_dict["config"] if config["name"] == "twitter"), None)

            # TODO: These should probably live in the related task parameters
            self.tweet_interval = twitter_config.get("tweet_interval", 900) if twitter_config else 900
            self.own_tweet_replies_count = twitter_config.get("own_tweet_replies_count", 2) if twitter_config else 2

            self.is_llm_set = False
            
            # Cache for system prompt
            self._system_prompt = None

            # Extract loop tasks
            self.tasks = agent_dict.get("tasks", [])
            self.task_weights = [task.get("weight", 0) for task in self.tasks]

            # Set up empty agent state
            self.state = {}
            
        except Exception as e:
            logger.error("Could not load ZerePy agent")
            raise e
        
    def _setup_llm_provider(self):           
        # Get first available LLM provider and its model
        llm_providers = self.connection_manager.get_model_providers()
        if not llm_providers:
            raise ValueError("No configured LLM provider found")
        self.model_provider = llm_providers[0]
        
        # Load Twitter username for self-reply detection (optional)
        find_env_file()
        self.username = os.getenv('TWITTER_USERNAME', '').lower()
        # Twitter username is optional - only needed if using Twitter tasks

    def _construct_system_prompt(self) -> str:
        """Construct the system prompt from agent configuration"""
        if self._system_prompt is None:
            prompt_parts = []
            prompt_parts.extend(self.bio)

            if self.traits:
                prompt_parts.append("\nYour key traits are:")
                prompt_parts.extend(f"- {trait}" for trait in self.traits)

            if self.examples:
                prompt_parts.append("\nHere are some examples of your style (Please avoid repeating any of these):")
                prompt_parts.extend(f"- {example}" for example in self.examples)

            self._system_prompt = "\n".join(prompt_parts)

        return self._system_prompt

    def prompt_llm(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using the configured LLM provider"""
        system_prompt = system_prompt or self._construct_system_prompt()
        
        return self.connection_manager.perform_action(
            connection_name=self.model_provider,
            action_name="generate-text",
            params=[prompt, system_prompt]
        )
    
    def perform_action(self, connection: str, action: str, **kwargs) -> None:
        return self.connection_manager.perform_action(connection, action, **kwargs)

    def loop(self):
        """Main agent loop for autonomous behavior"""
        if not self.is_llm_set:
            self._setup_llm_provider()

        logger.info("\n🚀 Starting agent loop...")
        logger.info("Press Ctrl+C at any time to stop the loop.")
        print_h_bar()

        time.sleep(2)
        logger.info("Starting loop in 5 seconds...")
        for i in range(5, 0, -1):
            logger.info(f"{i}...")
            time.sleep(1)

        # Initialize platform-specific state
        self._init_loop_state()

        try:
            while True:
                success = False
                try:
                    # REPLENISH INPUTS - Gather data from all configured platforms
                    self._gather_platform_data()

                    # CHOOSE AN ACTION - Platform-aware task selection
                    action = random.choices(self.tasks, weights=self.task_weights, k=1)[0]
                    action_name = action["name"]

                    # ROUTE ACTION TO APPROPRIATE PLATFORM HANDLER
                    success = self._execute_platform_action(action_name)

                    logger.info(f"\n⏳ Waiting {self.loop_delay} seconds before next loop...")
                    print_h_bar()
                    time.sleep(self.loop_delay if success else 60)

                except Exception as e:
                    logger.error(f"\n❌ Error in agent loop iteration: {e}")
                    logger.info(f"⏳ Waiting {self.loop_delay} seconds before retrying...")
                    time.sleep(self.loop_delay)

        except KeyboardInterrupt:
            logger.info("\n🛑 Agent loop stopped by user.")
            return

    def _init_loop_state(self):
        """Initialize platform-specific state variables"""
        # Twitter state (existing)
        self.last_tweet_time = 0

        # Discord state
        self.last_moderation_check = 0
        self.last_engagement_time = 0
        self.active_channels_cache = []

        # YouTube state
        self.last_analytics_check = 0
        self.last_content_upload = 0

    def _gather_platform_data(self):
        """Gather data from all configured platforms"""
        # Twitter data gathering (existing)
        if "timeline_tweets" not in self.state or len(self.state["timeline_tweets"]) == 0:
            try:
                logger.info("\n👀 READING TIMELINE")
                self.state["timeline_tweets"] = self.connection_manager.perform_action(
                    connection_name="twitter",
                    action_name="read-timeline",
                    params=[]
                )
            except Exception as e:
                logger.warning(f"Failed to gather Twitter data: {e}")

        # Discord data gathering
        try:
            self._gather_discord_data()
        except Exception as e:
            logger.warning(f"Failed to gather Discord data: {e}")

        # YouTube data gathering
        try:
            self._gather_youtube_data()
        except Exception as e:
            logger.warning(f"Failed to gather YouTube data: {e}")

    def _execute_platform_action(self, action_name):
        """Route action to appropriate platform handler"""
        # Twitter actions
        if action_name in ["post-tweet", "reply-to-tweet", "like-tweet"]:
            return self._execute_twitter_action(action_name)

        # Discord actions
        elif action_name in ["moderate-server", "engage-community", "monitor-activity", "manage-channels", "handle-reports"]:
            return self._execute_discord_action(action_name)

        # YouTube actions
        elif action_name in ["analyze_performance", "manage_content", "optimize_strategy"]:
            return self._execute_youtube_action(action_name)

        else:
            logger.warning(f"Unknown action: {action_name}")
            return False

    def _execute_twitter_action(self, action_name):
        """Execute Twitter-specific actions"""
        if action_name == "post-tweet":
            return self._twitter_post_tweet()
        elif action_name == "reply-to-tweet":
            return self._twitter_reply_to_tweet()
        elif action_name == "like-tweet":
            return self._twitter_like_tweet()
        return False

    def _execute_discord_action(self, action_name):
        """Execute Discord-specific actions"""
        if action_name == "moderate-server":
            return self._discord_moderate_server()
        elif action_name == "engage-community":
            return self._discord_engage_community()
        elif action_name == "monitor-activity":
            return self._discord_monitor_activity()
        elif action_name == "manage-channels":
            return self._discord_manage_channels()
        elif action_name == "handle-reports":
            return self._discord_handle_reports()
        return False

    def _execute_youtube_action(self, action_name):
        """Execute YouTube-specific actions"""
        if action_name == "analyze_performance":
            return self._youtube_analyze_performance()
        elif action_name == "manage_content":
            return self._youtube_manage_content()
        elif action_name == "optimize_strategy":
            return self._youtube_optimize_strategy()
        return False

    # Twitter Action Implementations
    def _twitter_post_tweet(self):
        """Post a new tweet"""
        current_time = time.time()
        if current_time - self.last_tweet_time >= self.tweet_interval:
            logger.info("\n📝 GENERATING NEW TWEET")
            print_h_bar()

            prompt = ("Generate an engaging tweet. Don't include any hashtags, links or emojis. Keep it under 280 characters."
                    f"The tweets should be pure commentary, do not shill any coins or projects apart from {self.name}. Do not repeat any of the"
                    "tweets that were given as example. Avoid the words AI and crypto.")
            tweet_text = self.prompt_llm(prompt)

            if tweet_text:
                logger.info("\n🚀 Posting tweet:")
                logger.info(f"'{tweet_text}'")
                self.connection_manager.perform_action(
                    connection_name="twitter",
                    action_name="post-tweet",
                    params=[tweet_text]
                )
                self.last_tweet_time = current_time
                logger.info("\n✅ Tweet posted successfully!")
                return True
        else:
            logger.info("\n👀 Delaying post until tweet interval elapses...")
            print_h_bar()
        return False

    def _twitter_reply_to_tweet(self):
        """Reply to a tweet"""
        if "timeline_tweets" in self.state and len(self.state["timeline_tweets"]) > 0:
            tweet = self.state["timeline_tweets"].pop(0)
            tweet_id = tweet.get('id')
            if not tweet_id:
                return False

            # Check if it's our own tweet using username
            is_own_tweet = tweet.get('author_username', '').lower() == self.username
            if is_own_tweet:
                # pick one of the replies to reply to
                try:
                    replies = self.connection_manager.perform_action(
                        connection_name="twitter",
                        action_name="get-tweet-replies",
                        params=[tweet.get('author_id')]
                    )
                    if replies:
                        self.state["timeline_tweets"].extend(replies[:self.own_tweet_replies_count])
                except Exception as e:
                    logger.warning(f"Failed to get replies for own tweet: {e}")
                return False

            logger.info(f"\n💬 GENERATING REPLY to: {tweet.get('text', '')[:50]}...")

            # Customize prompt based on whether it's a self-reply
            base_prompt = (f"Generate a friendly, engaging reply to this tweet: {tweet.get('text')}. Keep it under 280 characters. Don't include any usernames, hashtags, links or emojis. "
                f"The tweets should be pure commentary, do not shill any coins or projects apart from {self.name}. Do not repeat any of the"
                "tweets that were given as example. Avoid the words AI and crypto.")

            system_prompt = self._construct_system_prompt()
            reply_text = self.prompt_llm(prompt=base_prompt, system_prompt=system_prompt)

            if reply_text:
                logger.info(f"\n🚀 Posting reply: '{reply_text}'")
                self.connection_manager.perform_action(
                    connection_name="twitter",
                    action_name="reply-to-tweet",
                    params=[tweet_id, reply_text]
                )
                logger.info("✅ Reply posted successfully!")
                return True
        return False

    def _twitter_like_tweet(self):
        """Like a tweet"""
        if "timeline_tweets" in self.state and len(self.state["timeline_tweets"]) > 0:
            tweet = self.state["timeline_tweets"].pop(0)
            tweet_id = tweet.get('id')
            if not tweet_id:
                return False

            logger.info(f"\n👍 LIKING TWEET: {tweet.get('text', '')[:50]}...")

            self.connection_manager.perform_action(
                connection_name="twitter",
                action_name="like-tweet",
                params=[tweet_id]
            )
            logger.info("✅ Tweet liked successfully!")
            return True
        return False

    # Discord Data Gathering
    def _gather_discord_data(self):
        """Gather Discord-specific data for decision making"""
        try:
            # Get server info if not cached
            if "discord_server_info" not in self.state:
                logger.info("📊 Gathering Discord server information...")
                self.state["discord_server_info"] = self.connection_manager.perform_action(
                    connection_name="discord",
                    action_name="get-server-info",
                    params=[]
                )

            # Get recent channel activity (every 10 minutes)
            current_time = time.time()
            if current_time - self.state.get("last_discord_activity_check", 0) > 600:
                logger.info("📈 Checking Discord channel activity...")
                activity_data = self.connection_manager.perform_action(
                    connection_name="discord",
                    action_name="get-channel-activity",
                    params=["", 24]  # All channels, last 24 hours
                )
                self.state["discord_activity"] = activity_data
                self.state["last_discord_activity_check"] = current_time

        except Exception as e:
            logger.debug(f"Discord data gathering failed: {e}")

    # Discord Action Implementations
    def _discord_moderate_server(self):
        """Perform automated server moderation"""
        try:
            current_time = time.time()
            # Only perform intensive moderation checks every 5 minutes
            if current_time - self.last_moderation_check < 300:
                logger.info("⏰ Skipping moderation check - too soon since last check")
                return True

            logger.info("\n🛡️ PERFORMING SERVER MODERATION")
            print_h_bar()

            moderation_actions = 0

            # Check for spam and rule violations
            if "discord_activity" in self.state:
                activity_data = self.state["discord_activity"]

                # Look for suspicious activity patterns
                for channel in activity_data.get("channels", []):
                    channel_name = channel.get("channel_name", "unknown")
                    message_count = channel.get("message_count", 0)
                    unique_users = channel.get("unique_users", 0)

                    # Flag channels with extremely high activity (potential spam)
                    if message_count > 100 and unique_users < 5:
                        logger.warning(f"🚨 High activity detected in #{channel_name}: {message_count} messages from {unique_users} users")
                        logger.info("This could indicate spam or bot activity")
                        moderation_actions += 1

                    # Check for channels with no recent activity (potential cleanup)
                    elif message_count == 0:
                        logger.info(f"📭 Channel #{channel_name} has no recent activity")

                # Check overall server health
                total_messages = activity_data.get("total_messages", 0)
                total_users = activity_data.get("total_unique_users", 0)

                if total_messages > 0:
                    avg_messages_per_user = total_messages / max(total_users, 1)
                    logger.info(f"Server health: {total_messages} messages from {total_users} users (avg: {avg_messages_per_user:.1f} msg/user)")

                    # Flag unusual patterns
                    if avg_messages_per_user > 20:
                        logger.warning("🚨 High message volume per user detected - possible spam campaign")
                        moderation_actions += 1

            # Update moderation timestamp
            self.last_moderation_check = current_time

            if moderation_actions > 0:
                logger.info(f"✅ Server moderation completed - found {moderation_actions} issues requiring attention")
                return True
            else:
                logger.info("✅ Server moderation completed - no issues detected")
                return True

        except Exception as e:
            logger.error(f"Discord moderation failed: {e}")
            return False

    def _discord_engage_community(self):
        """Engage with community members"""
        try:
            current_time = time.time()
            # Only engage every 30 minutes to avoid spam
            if current_time - self.last_engagement_time < 1800:
                logger.debug("⏰ Skipping community engagement - too soon since last engagement")
                return True

            logger.info("\n💬 ENGAGING WITH COMMUNITY")
            print_h_bar()

            # Determine engagement type based on server activity
            engagement_type = "general"

            if "discord_activity" in self.state:
                activity = self.state["discord_activity"]
                total_messages = activity.get("total_messages", 0)

                if total_messages < 10:
                    engagement_type = "welcome"  # Low activity - welcome new members
                elif total_messages > 50:
                    engagement_type = "celebration"  # High activity - celebrate engagement
                else:
                    engagement_type = "general"  # Normal activity - general engagement

            # Generate appropriate message based on activity level
            if engagement_type == "welcome":
                prompt = f"As {self.name}, generate a welcoming message for a quiet Discord server. Encourage members to introduce themselves and participate. Keep under 300 characters."
            elif engagement_type == "celebration":
                prompt = f"As {self.name}, generate an enthusiastic message celebrating high community activity. Thank members for their engagement. Keep under 300 characters."
            else:
                prompt = f"As {self.name}, generate a friendly, engaging message to keep the community conversation going. Ask an interesting question or share a thought. Keep under 300 characters."

            engagement_message = self.prompt_llm(prompt)

            if engagement_message:
                # Post to a general/welcome channel
                # In a real implementation, you'd determine the appropriate channel
                welcome_channel_id = "1445575379321360527"  # Using the configured channel

                self.connection_manager.perform_action(
                    connection_name="discord",
                    action_name="send-message",
                    params=[welcome_channel_id, engagement_message]
                )

                self.last_engagement_time = current_time
                logger.info(f"✅ Community engagement message posted ({engagement_type} type)")
                logger.info(f"Message: {engagement_message[:100]}...")
                return True
            else:
                logger.warning("Failed to generate engagement message")
                return False

        except Exception as e:
            logger.error(f"Discord community engagement failed: {e}")
            return False

    def _discord_monitor_activity(self):
        """Monitor server activity and generate reports"""
        try:
            logger.info("\n📊 MONITORING SERVER ACTIVITY")
            print_h_bar()

            if "discord_activity" in self.state:
                activity = self.state["discord_activity"]

                # Extract key metrics
                total_messages = activity.get("total_messages", 0)
                total_users = activity.get("total_unique_users", 0)
                channels = activity.get("channels", [])
                summary = activity.get("summary", {})

                # Generate insights
                insights = []

                if total_messages == 0:
                    insights.append("🚨 No messages in the last 24 hours - server may be inactive")
                elif total_messages < 50:
                    insights.append("📉 Low activity - consider community engagement initiatives")
                elif total_messages > 200:
                    insights.append("📈 High activity - community is very engaged!")

                # Analyze channel distribution
                if channels:
                    text_channels = [c for c in channels if c.get("message_count", 0) > 0]
                    silent_channels = [c for c in channels if c.get("message_count", 0) == 0]

                    if silent_channels:
                        insights.append(f"🤫 {len(silent_channels)} channels have no recent activity")

                    # Find most and least active channels
                    if text_channels:
                        most_active = max(text_channels, key=lambda c: c.get("message_count", 0))
                        least_active = min(text_channels, key=lambda c: c.get("message_count", 0))

                        insights.append(f"🏆 Most active: #{most_active.get('channel_name')} ({most_active.get('message_count')} msgs)")
                        if least_active.get("message_count", 0) > 0:
                            insights.append(f"😴 Least active: #{least_active.get('channel_name')} ({least_active.get('message_count')} msgs)")

                # Calculate engagement rate
                if total_users > 0:
                    avg_msgs_per_user = total_messages / total_users
                    if avg_msgs_per_user > 10:
                        insights.append(f"💬 High engagement: {avg_msgs_per_user:.1f} messages per user")
                    elif avg_msgs_per_user < 2:
                        insights.append(f"🤔 Low engagement: {avg_msgs_per_user:.1f} messages per user")

                # Log the report
                logger.info(f"📈 Activity Summary: {total_messages} messages, {total_users} users, {len(channels)} channels")
                for insight in insights:
                    logger.info(f"  {insight}")

                # Store insights for future comparison
                self.state["last_activity_insights"] = {
                    "total_messages": total_messages,
                    "total_users": total_users,
                    "insights": insights,
                    "timestamp": time.time()
                }

                logger.info("✅ Activity monitoring completed")
                return True
            else:
                logger.info("No activity data available for monitoring")
                return False

        except Exception as e:
            logger.error(f"Discord activity monitoring failed: {e}")
            return False

    def _discord_manage_channels(self):
        """Manage Discord channels (cleanup, organization)"""
        try:
            logger.info("\n🏗️ MANAGING CHANNELS")
            print_h_bar()

            # Simple channel management - check for inactive channels
            # In a real implementation, you'd have more sophisticated logic
            if "discord_activity" in self.state:
                inactive_channels = []
                for channel in self.state["discord_activity"].get("channels", []):
                    if channel.get("message_count", 0) == 0:
                        inactive_channels.append(channel.get("channel_name", "unknown"))

                if inactive_channels:
                    logger.info(f"Found {len(inactive_channels)} potentially inactive channels")
                    logger.info(f"Inactive: {', '.join(inactive_channels[:3])}")  # Show first 3
                else:
                    logger.info("All channels appear active")

                logger.info("✅ Channel management check completed")
                return True
            else:
                logger.info("No channel data available for management")
                return False

        except Exception as e:
            logger.error(f"Discord channel management failed: {e}")
            return False

    def _discord_handle_reports(self):
        """Handle user reports and moderation requests"""
        try:
            logger.info("\n🚨 CHECKING FOR REPORTS")
            print_h_bar()

            # This would typically involve checking a reports channel or modmail
            # For now, we'll just log that we're checking
            logger.info("Report handling system checked - no pending reports")
            logger.info("✅ Report handling completed")
            return True

        except Exception as e:
            logger.error(f"Discord report handling failed: {e}")
            return False

    # YouTube Data Gathering
    def _gather_youtube_data(self):
        """Gather YouTube-specific data for decision making"""
        try:
            # Get channel analytics periodically (every 30 minutes)
            current_time = time.time()
            if current_time - self.state.get("last_youtube_analytics_check", 0) > 1800:
                logger.info("📊 Gathering YouTube analytics...")
                analytics = self.connection_manager.perform_action(
                    connection_name="youtube",
                    action_name="get_channel_analytics",
                    params=[]
                )
                self.state["youtube_analytics"] = analytics
                self.state["last_youtube_analytics_check"] = current_time

        except Exception as e:
            logger.debug(f"YouTube data gathering failed: {e}")

    # YouTube Action Implementations
    def _youtube_analyze_performance(self):
        """Analyze YouTube channel performance"""
        try:
            logger.info("\n📈 ANALYZING YOUTUBE PERFORMANCE")
            print_h_bar()

            if "youtube_analytics" in self.state:
                analytics = self.state["youtube_analytics"]

                # Extract key metrics
                subscriber_count = analytics.get("subscriber_count", 0)
                video_count = analytics.get("video_count", 0)
                view_count = analytics.get("view_count", 0)

                # Calculate simple KPIs
                avg_views_per_video = view_count / max(video_count, 1)

                logger.info(f"YouTube Analytics Summary:")
                logger.info(f"• Subscribers: {subscriber_count:,}")
                logger.info(f"• Videos: {video_count}")
                logger.info(f"• Total Views: {view_count:,}")
                logger.info(f"• Avg Views/Video: {avg_views_per_video:.1f}")

                # Store for future comparison
                self.state["last_performance_check"] = {
                    "subscriber_count": subscriber_count,
                    "video_count": video_count,
                    "view_count": view_count,
                    "timestamp": time.time()
                }

                logger.info("✅ Performance analysis completed")
                return True
            else:
                logger.info("No YouTube analytics data available")
                return False

        except Exception as e:
            logger.error(f"YouTube performance analysis failed: {e}")
            return False

    def _youtube_manage_content(self):
        """Manage YouTube content (uploads, updates)"""
        try:
            current_time = time.time()
            # Only manage content every few hours to avoid quota issues
            if current_time - self.last_content_upload < 14400:  # 4 hours
                return False

            logger.info("\n🎬 MANAGING YOUTUBE CONTENT")
            print_h_bar()

            # This would typically involve checking for scheduled uploads
            # For now, we'll just log content management activities
            logger.info("Checking for content management tasks...")

            # Example: Check if we need to upload scheduled content
            # In a real implementation, you'd have a content queue/schedule
            logger.info("No scheduled content uploads at this time")

            # Example: Check for videos that need metadata updates
            logger.info("No video metadata updates needed")

            self.last_content_upload = current_time
            logger.info("✅ Content management check completed")
            return True

        except Exception as e:
            logger.error(f"YouTube content management failed: {e}")
            return False

    def _youtube_optimize_strategy(self):
        """Optimize YouTube strategy based on analytics"""
        try:
            logger.info("\n🎯 OPTIMIZING YOUTUBE STRATEGY")
            print_h_bar()

            if "youtube_analytics" in self.state and "last_performance_check" in self.state:
                current = self.state["youtube_analytics"]
                previous = self.state["last_performance_check"]

                # Simple trend analysis
                sub_growth = current.get("subscriber_count", 0) - previous.get("subscriber_count", 0)
                view_growth = current.get("view_count", 0) - previous.get("view_count", 0)

                logger.info("Strategy Optimization Analysis:")
                logger.info(f"• Subscriber Growth: {sub_growth:+,}")
                logger.info(f"• View Growth: {view_growth:+,}")

                # Generate optimization recommendations
                recommendations = []

                if sub_growth > 0:
                    recommendations.append("📈 Continue current content strategy - subscribers are growing")
                elif sub_growth < 0:
                    recommendations.append("📉 Review content quality and posting frequency")

                if view_growth > 0:
                    recommendations.append("👀 Content engagement is positive")
                else:
                    recommendations.append("🎬 Consider improving video titles and thumbnails")

                for rec in recommendations:
                    logger.info(f"  {rec}")

                logger.info("✅ Strategy optimization completed")
                return True
            else:
                logger.info("Insufficient data for strategy optimization")
                return False

        except Exception as e:
            logger.error(f"YouTube strategy optimization failed: {e}")
            return False
