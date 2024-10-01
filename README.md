# Discord Service Monitor Bot

This Python bot monitors system services on an Ubuntu machine using the `/etc/systemd/system/*.service` files and provides real-time status updates via a Discord bot. The bot is capable of starting, stopping, and restarting services directly through Discord interactions.

## Features

- Monitors services under `/etc/systemd/system/*.service`.
- Displays service status and dynamically updates service status in Discord messages.
- Provides a dropdown for selecting services and controlling them (start, stop, restart).
- Periodically updates the status of services and the overall system status every 10 seconds.
- Dynamically changes the Discord channel name based on overall service health.
- Clears the channel on bot startup.

## Requirements

- Python 3.8 or higher
- A Discord bot with appropriate permissions (manage channel, send messages, etc.).
- The following Python libraries:
  - `discord.py`
  - `python-dotenv`

You can install the required libraries by running:

```bash
pip install discord.py python-dotenv
```
## Configuration
### Step 1: Create a `.env` file
Create a `.env` file in the same directory as the bot script. The file should contain the following variables:
```bash
DISCORD_BOT_TOKEN=
DISCORD_CHANNEL_ID=
SERVICE_CHECK_RATE=10
CHANNEL_PRECEDING_CHARACTER=┏
SERVICE_USER=
```
Replace `<your_discord_bot_token>` with the actual token of your Discord bot and `<your_discord_channel_id>` with the ID of the channel where the bot will send status updates.

### Step 2: Modify sudo permissions (optional)
If your bot requires sudo to start, stop, or restart services, you need to allow the bot user to run systemctl without a password. To do this, follow these steps:

1. Open the sudoers file:
```bash
sudo visudo
```
2. Add the following line to allow the bot user (replace `botuser` with your actual username) to run systemctl without a password:
```css
botuser ALL=(ALL) NOPASSWD: /bin/systemctl
```
### Step 3: Run the Bot
To run the bot, use the following command:
```bash
python3 missioncontrol.py
```
## How the Bot Works
### Service Monitoring
- The bot monitors services located under /etc/systemd/system/ and only considers .service files that include a User= directive.
- The bot provides the following real-time status information:
-- 🟢 for active services
-- 🔴 for failed or inactive services
-- 🟡 for services with unknown or transitional states
## Interaction Features
- Service Dropdown: Users can select a service from the dropdown to view details and control the service (start, stop, restart).
- Automatic Updates: The bot updates the service status in the channel every 10 seconds.
- Channel Name Update: The channel name reflects the overall health of the services:
-- 🟢 if all services are running.
-- 🟡 if some services are in an unknown state.
-- 🔴 if any service has failed or is inactive.
## Commands and Buttons
The bot provides buttons for:
- Start - Starts a selected service.
- Stop - Stops a running service.
- Restart - Restarts a running service.
# Example Workflow
1. When the bot starts, it clears the Discord channel.
2. The bot checks for services under /etc/systemd/system/*.service and monitors their status.
3. It displays the current status of all relevant services in the channel and provides a dropdown for interaction.
4. Every 10 seconds, the status is updated, and if necessary, the bot modifies the channel name to reflect the overall status of the services.
## Troubleshooting
### Sudo Requires Password
If you encounter issues where the bot cannot start, stop, or restart services because sudo requires a password, ensure that you have configured the sudoers file to allow the bot user to run systemctl without a password.
## Missing Permissions
Ensure that your Discord bot has the following permissions:
- Manage Channel
- Read Messages
- Send Messages
- Embed Links
- Add Reactions
## Discord API Rate Limits
If the bot updates the status too frequently, you may encounter Discord's rate limits. You can adjust the update frequency by modifying the `@tasks.loop(seconds=10)` decorator in the script.
