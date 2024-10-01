import asyncio
import discord
from discord.ext import commands, tasks
import subprocess
from dotenv import load_dotenv
import os
import re
import glob

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
SERVICE_CHECK_RATE = int(os.getenv('SERVICE_CHECK_RATE'), 10)
CHANNEL_PRECEDING_CHARACTER = os.getenv('CHANNEL_PRECEDING_CHARACTER', '')
SERVICE_USER = os.getenv('SERVICE_USER')
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

def get_status_emoji(status_message):
    if 'active (running)' in status_message:
        return '🟢'
    elif 'inactive' in status_message or 'failed' in status_message:
        return '🔴'
    else:
        return '🟡'

def get_services_from_systemd():
    service_files = glob.glob('/etc/systemd/system/*.service')
    services = [os.path.basename(service) for service in service_files]
    return services

def get_enabled_services_with_user():
    services = get_services_from_systemd()
    services_with_user = []
    for service in services:
        service_status = subprocess.run(['systemctl', 'cat', service], capture_output=True, text=True)
        if re.search(rf'^User={SERVICE_USER}', service_status.stdout, re.MULTILINE):
            services_with_user.append(service)
    if not services_with_user:
        print(f"No services found for user: {SERVICE_USER}")
    return sorted(services_with_user)


def get_service_status_and_description(service):
    result_status = subprocess.run(['systemctl', 'status', service], capture_output=True, text=True)
    result_description = subprocess.run(['systemctl', 'cat', service], capture_output=True, text=True)
    status = result_status.stdout
    description_match = re.search(r'^Description=(.*)', result_description.stdout, re.MULTILINE)
    description = description_match.group(1) if description_match else "No description available"
    return status, description

async def update_channel_name(channel, overall_status_emoji):
    if not CHANNEL_PRECEDING_CHARACTER:
        new_name = f'{overall_status_emoji}status'
    else:
        new_name = f'{CHANNEL_PRECEDING_CHARACTER}{overall_status_emoji}status'
    if channel.name != new_name:
        await channel.edit(name=new_name)

class ServiceDropdown(discord.ui.Select):
    def __init__(self, services):
        options = [discord.SelectOption(label=service) for service in services[:25]]
        super().__init__(placeholder="Select a Service", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        service = self.values[0]
        status, description = get_service_status_and_description(service)
        emoji = get_status_emoji(status)
        if 'active (running)' in status:
            view = ServiceControlButtons(service, show_start=False)
        else:
            view = ServiceControlButtons(service, show_stop_restart=False)
        
        await interaction.response.send_message(f"{emoji} **{service}:** - ({description})\n```{status}```", view=view, ephemeral=True)

class ServiceControlButtons(discord.ui.View):
    def __init__(self, service, show_start=True, show_stop_restart=True):
        super().__init__()
        self.service = service
        if show_start:
            start_button = discord.ui.Button(label='Start', style=discord.ButtonStyle.green, custom_id=f'start_{service}')
            start_button.callback = self.start_service
            self.add_item(start_button)
        if show_stop_restart:
            stop_button = discord.ui.Button(label='Stop', style=discord.ButtonStyle.red, custom_id=f'stop_{service}')
            stop_button.callback = self.stop_service
            self.add_item(stop_button)
            restart_button = discord.ui.Button(label='Restart', style=discord.ButtonStyle.blurple, custom_id=f'restart_{service}')
            restart_button.callback = self.restart_service
            self.add_item(restart_button)

    async def start_service(self, interaction: discord.Interaction):
        subprocess.run(['sudo', 'systemctl', 'start', self.service])
        await interaction.response.send_message(f'{self.service} started.', ephemeral=True)

    async def stop_service(self, interaction: discord.Interaction):
        subprocess.run(['sudo', 'systemctl', 'stop', self.service])
        await interaction.response.send_message(f'{self.service} stopped.', ephemeral=True)

    async def restart_service(self, interaction: discord.Interaction):
        subprocess.run(['sudo', 'systemctl', 'restart', self.service])
        await interaction.response.send_message(f'{self.service} restarted.', ephemeral=True)

bot = commands.Bot(command_prefix='!', intents=intents)
status_message = None

async def clear_channel(channel):
    print(f"clear channel: {channel.name}")
    async for message in channel.history(limit=None):
        try:
            await message.delete()
            await asyncio.sleep(2)
        except Exception as e:
            print(f"error deleting a message: {e}")

@tasks.loop(seconds=SERVICE_CHECK_RATE)
async def update_service_status():
    global status_message
    services = get_enabled_services_with_user()
    status_messages = []
    overall_status = '🟢'

    for service in services[:25]:
        status, description = get_service_status_and_description(service)
        emoji = get_status_emoji(status)
        status_messages.append(f"{emoji} **{service}:** - ({description})")
        if emoji == '🔴':
            overall_status = '🔴'
        elif emoji == '🟡' and overall_status != '🔴':
            overall_status = '🟡'
    if status_message:
        dropdown = ServiceDropdown(services)
        view = discord.ui.View()
        view.add_item(dropdown)
        await status_message.edit(content="Service Overview:\n" + "\n".join(status_messages), view=view)
        channel = status_message.channel
        await update_channel_name(channel, overall_status)

async def send_service_status(channel):
    global status_message
    services = sorted(get_enabled_services_with_user())
    if not services:
        await channel.send("No services found for the specified user.")
        return
    status_messages = []
    overall_status = '🟢'
    for service in services[:25]:
        status, description = get_service_status_and_description(service)
        emoji = get_status_emoji(status)
        status_messages.append(f"{emoji} **{service}:** - ({description})")
        if emoji == '🔴':
            overall_status = '🔴'
        elif emoji == '🟡' and overall_status != '🔴':
            overall_status = '🟡'
    dropdown = ServiceDropdown(services)
    view = discord.ui.View()
    view.add_item(dropdown)
    status_message = await channel.send("Service Overview:\n" + "\n".join(status_messages), view=view)
    await update_channel_name(channel, overall_status)
    update_service_status.start()

@bot.event
async def on_ready():
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    await clear_channel(channel)
    await send_service_status(channel)
    print(f'Bot logged in in Channel-ID {DISCORD_CHANNEL_ID}')

bot.run(DISCORD_BOT_TOKEN)
