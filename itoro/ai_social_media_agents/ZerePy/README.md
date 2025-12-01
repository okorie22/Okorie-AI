# ZerePy

ZerePy is an open-source Python framework designed to let you deploy your own agents on social media platforms, powered by OpenAI or Anthropic LLMs.

ZerePy is built from a modularized version of the Zerebro backend. With ZerePy, you can launch your own agent with
similar core functionality as Zerebro. For creative outputs, you'll need to fine-tune your own model.

## Features
- CLI interface for managing agents
- **Twitter/X integration** - Post tweets, reply, like, and read timeline
- **Discord integration** - Complete server management, moderation, and community engagement
- **YouTube integration** - Full channel management, video uploads, analytics, and live streaming
- OpenAI/Anthropic LLM support
- Modular connection system

## Quickstart

The quickest way to start using ZerePy is to use our Replit template:

https://replit.com/@blormdev/ZerePy?v=1

1. Fork the template (you will need you own Replit account)
2. Click the run button on top
3. Voila! your CLI should be ready to use, you can jump to the configuration section

## Requirements

System:
- Python 3.10 or higher
- Poetry 1.5 or higher

API keys:
  - LLM: make an account and grab an API key
      + OpenAI: https://platform.openai.com/api-keys.
      + Anthropic: https://console.anthropic.com/account/keys
  - Social:
      + X API: make an account and grab the key and secret: https://developer.x.com/en/docs/authentication/oauth-1-0a/api-key-and-secret
      + Discord Bot: create a bot at https://discord.com/developers/applications and get the bot token
      + YouTube API: create OAuth 2.0 credentials at https://console.developers.google.com/ and enable YouTube Data API v3

## Installation

1. First, install Poetry for dependency management if you haven't already:

Follow the steps here to use the official installation: https://python-poetry.org/docs/#installing-with-the-official-installer

2. Clone the repository:
```bash
git clone https://github.com/blorm-network/ZerePy.git
```

3. Go to the `zerepy` directory:
```bash
cd zerepy
```

4. Install dependencies:
```bash
poetry install --no-root
```

This will create a virtual environment and install all required dependencies.

## Usage

1. Activate the virtual environment:
```bash
poetry shell
```

2. Run the application:
```bash
poetry run python main.py
```

## Configure connections & launch an agent

1. Configure your connections:
   ```
   configure-connection twitter
   configure-connection discord
   configure-connection youtube
   configure-connection openai
   ```
4. Load your agent (usually one is loaded by default, which can be set using the CLI or in agents/general.json):
   ```
   load-agent example
   load-agent discord_manager  # For Discord management
   load-agent youtube_manager  # For YouTube management
   ```
5. Start your agent:
   ```
   start
   ```

## Create your own agent

The secret to having a good output from the agent is to provide as much detail as possible in the configuration file. Craft a story and a context for the agent, and pick very good examples of tweets to include.

If you want to take it a step further, you can fine tune your own model: https://platform.openai.com/docs/guides/fine-tuning.

## Discord Server Management

ZerePy includes comprehensive Discord server management capabilities. Your AI agent can:

**Server Administration:**
- Create and manage channels (text, voice, categories)
- Manage roles and permissions
- Handle member moderation (kick, ban, timeout)
- Configure auto-moderation and spam prevention

**Community Engagement:**
- Send automated welcome messages
- Create polls and scheduled events
- Monitor server activity and engagement
- Generate community reports

**Content Moderation:**
- Delete inappropriate messages
- Bulk message management
- User behavior monitoring
- Custom moderation rules

### Discord Agent Configuration

Create a new JSON file in the `agents` directory following this structure for Discord management:

```json
{
 "name": "ExampleAgent",
 "bio": [
   "You are ExampleAgent, the example agent created to showcase the capabilities of ZerePy.",
   "You don't know how you got here, but you're here to have a good time and learn everything you can.",
   "You are naturally curious, and ask a lot of questions."
  ],
  "traits": [
    "Curious",
    "Creative",
    "Innovative",
    "Funny"
  ],
  "examples": [
    "This is an example tweet.",
    "This is another example tweet."
  ],
  "loop_delay": 60,
  "config": [
    {
      "name": "twitter",
      "timeline_read_count": 10,
      "tweet_interval": 900,
      "own_tweet_replies_count":2
    },
    {
      "name": "openai",
      "model": "gpt-3.5-turbo"
    },
    {
      "name": "anthropic",
      "model": "claude-3-5-sonnet-20241022"
    }
  ],
  "tasks": [
    {"name": "post-tweet", "weight": 1},
    {"name": "reply-to-tweet", "weight": 1},
    {"name": "like-tweet", "weight": 1}
  ]
}

### Discord Agent Example

For Discord server management, use this configuration structure:

```json
{
  "name": "DiscordServerManager",
  "bio": [
    "You are an AI-powered Discord server manager responsible for maintaining a healthy, engaging, and well-moderated community.",
    "Your primary goals are to ensure smooth server operations, handle moderation tasks, and maintain a positive environment."
  ],
  "traits": ["Professional", "Fair", "Proactive", "Organized", "Helpful"],
  "examples": [
    "Welcome to our server! Please read the rules in #rules and introduce yourself in #introductions.",
    "I've temporarily muted this user for spamming. Let's keep our conversations clean and respectful."
  ],
  "loop_delay": 60,
  "config": [
    {
      "name": "discord",
      "guild_id": "123456789012345678",
      "command_prefix": "!",
      "log_channel_id": "123456789012345678",
      "welcome_channel_id": "123456789012345678",
      "auto_mod_enabled": true,
      "spam_threshold": 5
    },
    {
      "name": "openai",
      "model": "gpt-4"
    }
  ],
  "tasks": [
    {"name": "moderate-server", "weight": 4},
    {"name": "engage-community", "weight": 3},
    {"name": "monitor-activity", "weight": 2}
  ]
}
```
```

## YouTube Channel Management

ZerePy includes comprehensive YouTube channel management capabilities. Your AI agent can:

**Video Management:**
- Upload videos with custom metadata, thumbnails, and scheduling
- Update video titles, descriptions, tags, and privacy settings
- Delete videos and manage video library
- Set custom thumbnails and optimize video presentation

**Playlist Management:**
- Create and manage playlists with custom descriptions
- Add/remove videos from playlists with position control
- Organize content for better viewer navigation
- Bulk playlist operations

**Community Engagement:**
- Moderate comments with approval/rejection/deletion
- Reply to comments automatically or manually
- Monitor comment analytics and engagement patterns
- Bulk comment moderation operations

**Analytics & Optimization:**
- Comprehensive channel and video performance metrics
- Audience demographics and geographic data
- Revenue analytics and monetization insights
- Content strategy recommendations based on data

**Live Streaming:**
- Schedule and manage live broadcasts
- Monitor live chat and audience interaction
- Stream analytics and performance tracking
- Automated stream management and moderation

**Channel Administration:**
- Update channel branding, banner, and description
- Manage channel settings and privacy options
- Feature channels and optimize channel layout
- Bulk operations across multiple videos

### YouTube Agent Configuration

For YouTube channel management, use this configuration structure:

```json
{
  "name": "YouTubeChannelManager",
  "bio": [
    "I am an AI-powered YouTube channel manager responsible for content strategy, engagement, and growth optimization.",
    "My goals include uploading high-quality content, managing community interactions, analyzing performance, and maximizing channel growth."
  ],
  "traits": ["Strategic", "Data-driven", "Community-focused", "Creative", "Analytical"],
  "loop_delay": 300,
  "config": [
    {
      "name": "youtube",
      "auto_upload_enabled": true,
      "comment_moderation": "auto",
      "analytics_reporting": true,
      "live_stream_management": true
    },
    {
      "name": "openai",
      "model": "gpt-4"
    }
  ],
  "tasks": [
    {"name": "analyze_performance", "weight": 4},
    {"name": "moderate_comments", "weight": 3},
    {"name": "engage_community", "weight": 3}
  ]
}
```

---

Made with ♥ @Blorm.xyz
