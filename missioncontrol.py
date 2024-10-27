import asyncio
import discord
from discord.ext import commands, tasks
import subprocess
import logging
from dotenv import load_dotenv
from datetime import datetime
import locale
import os
import re
import glob

# Logging einrichten
logging.basicConfig(
    filename='bot_log.log',  # Log-Datei
    filemode='a',            # Anhängen an die Datei
    format='%(asctime)s - %(levelname)s - %(message)s',  # Format der Log-Einträge
    level=logging.INFO       # Mindest-Level: INFO (alternativ DEBUG, ERROR)
)

# Log-Meldung, dass der Bot gestartet wird
logging.info("Starting bot...")

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

def get_docker_status_emoji(status):
    if 'Up' in status:
        return '🟢'
    elif 'Exited' in status or 'Restarting' in status:
        return '🔴'
    else:
        return '🟡'

def get_services_from_systemd():
    service_files = glob.glob('/etc/systemd/system/*.service')
    services = [os.path.basename(service) for service in service_files]
    logging.info(f"Found {len(services)} services from systemd.")
    return services

def get_enabled_services_with_user():
    services = get_services_from_systemd()
    services_with_user = []
    for service in services:
        service_status = subprocess.run(['systemctl', 'cat', service], capture_output=True, text=True)
        if re.search(rf'^User={SERVICE_USER}', service_status.stdout, re.MULTILINE):
            services_with_user.append(service)
    if not services_with_user:
        logging.warning(f"No services found for user: {SERVICE_USER}")
    return sorted(services_with_user)

def get_service_status_and_description(service):
    result_status = subprocess.run(['systemctl', 'status', service], capture_output=True, text=True)
    result_description = subprocess.run(['systemctl', 'cat', service], capture_output=True, text=True)
    status = result_status.stdout.splitlines()[:6]
    status = "\n".join(status)
    description_match = re.search(r'^Description=(.*)', result_description.stdout, re.MULTILINE)
    description = description_match.group(1) if description_match else "No description available"
    return status, description

def get_docker_containers():
    result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}: {{.Status}}'], capture_output=True, text=True)
    containers = result.stdout.splitlines()
    logging.info(f"Found {len(containers)} Docker containers.")
    return containers

# Docker Control Buttons für Container-Interaktionen
class DockerControlButtons(discord.ui.View):
    def __init__(self, container_name, show_start=True, show_stop_restart=True):
        super().__init__()
        self.container_name = container_name
        if show_start:
            start_button = discord.ui.Button(label='Start', style=discord.ButtonStyle.green, custom_id=f'start_{container_name}')
            start_button.callback = self.start_container
            self.add_item(start_button)
        if show_stop_restart:
            stop_button = discord.ui.Button(label='Stop', style=discord.ButtonStyle.red, custom_id=f'stop_{container_name}')
            stop_button.callback = self.stop_container
            self.add_item(stop_button)
            restart_button = discord.ui.Button(label='Restart', style=discord.ButtonStyle.blurple, custom_id=f'restart_{container_name}')
            restart_button.callback = self.restart_container
            self.add_item(restart_button)

    async def start_container(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        subprocess.run(['docker', 'start', self.container_name])
        await asyncio.sleep(5)
        logging.info(f"{self.container_name} Docker container started.")
        await interaction.followup.send(f'{self.container_name} started.', ephemeral=True)

    async def stop_container(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        subprocess.run(['docker', 'stop', self.container_name])
        await asyncio.sleep(5)
        logging.info(f"{self.container_name} Docker container stopped.")
        await interaction.followup.send(f'{self.container_name} stopped.', ephemeral=True)

    async def restart_container(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        subprocess.run(['docker', 'restart', self.container_name])
        await asyncio.sleep(5)
        logging.info(f"{self.container_name} Docker container restarted.")
        await interaction.followup.send(f'{self.container_name} restarted.', ephemeral=True)

# Service Control Buttons für systemd Service-Interaktionen
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
        await interaction.response.defer(ephemeral=True)
        subprocess.run(['sudo', 'systemctl', 'start', self.service])
        await asyncio.sleep(5)
        logging.info(f"{self.service} systemd service started.")
        await interaction.followup.send(f'{self.service} started.', ephemeral=True)

    async def stop_service(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        subprocess.run(['sudo', 'systemctl', 'stop', self.service])
        await asyncio.sleep(5)
        logging.info(f"{self.service} systemd service stopped.")
        await interaction.followup.send(f'{self.service} stopped.', ephemeral=True)

    async def restart_service(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        subprocess.run(['sudo', 'systemctl', 'restart', self.service])
        await asyncio.sleep(5)
        logging.info(f"{self.service} systemd service restarted.")
        await interaction.followup.send(f'{self.service} restarted.', ephemeral=True)

# Dropdown-Menü zur Auswahl von Services und Docker-Containern
class ServiceDropdown(discord.ui.Select):
    def __init__(self, services, containers):
        service_options = [discord.SelectOption(label=f'Service: {service}') for service in services[:25]]
        docker_options = [discord.SelectOption(label=f'Docker: {container.split(": ")[0]}') for container in containers[:25]]
        super().__init__(placeholder="Select a Service or Docker Container", min_values=1, max_values=1, options=service_options + docker_options)

    async def callback(self, interaction: discord.Interaction):
        selected_item = self.values[0]
        if selected_item.startswith('Docker'):
            container_name = selected_item.split('Docker: ')[1]
            container_status = next((status for name, status in [c.split(': ', 1) for c in get_docker_containers()] if name == container_name), None)
            if container_status:
                emoji = get_docker_status_emoji(container_status)
                if 'Up' in container_status:
                    view = DockerControlButtons(container_name, show_start=False)
                else:
                    view = DockerControlButtons(container_name, show_stop_restart=False)
                await interaction.response.send_message(f"{emoji} **Docker {container_name}:**\n```{container_status}```", view=view, ephemeral=True)
            else:
                logging.warning(f"Unexpected format in Docker container status: {selected_item}")
        else:
            service = selected_item.split('Service: ')[1]
            status, description = get_service_status_and_description(service)
            emoji = get_status_emoji(status)
            if 'active (running)' in status:
                view = ServiceControlButtons(service, show_start=False)
            else:
                view = ServiceControlButtons(service, show_stop_restart=False)
            await interaction.response.send_message(f"{emoji} **{service}:** - ({description})\n```{status}```", view=view, ephemeral=True)

bot = commands.Bot(command_prefix='!', intents=intents)

status_message = None

async def clear_channel(channel):
    async for message in channel.history(limit=None):
        try:
            await message.delete()
            await asyncio.sleep(60)
        except Exception as e:
            logging.error(f"Error deleting a message: {e}")

locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')

def format_last_refresh():
    now = datetime.now()
    formatted_time = now.strftime('%H:%M')
    return f"Last Refresh • heute um {formatted_time} Uhr"

@tasks.loop(seconds=SERVICE_CHECK_RATE)
async def update_service_status():
    global status_message
    services = get_enabled_services_with_user()
    docker_containers = get_docker_containers()
    status_messages = []
    overall_status = '🟢'

    status_messages.append("**Service Overview**")
    for service in services[:25]:
        status, description = get_service_status_and_description(service)
        emoji = get_status_emoji(status)
        status_messages.append(f"{emoji} **{service}:** - ({description})")
        if emoji == '🔴':
            overall_status = '🔴'
        elif emoji == '🟡' and overall_status != '🔴':
            overall_status = '🟡'

    status_messages.append("\n**Docker Overview**")
    for container in docker_containers:
        split_result = container.split(": ", 1)
        if len(split_result) == 2:
            name, status = split_result
            emoji = get_docker_status_emoji(status)
            status_messages.append(f"{emoji} **Docker {name}:** - ({status})")
            if emoji == '🔴':
                overall_status = '🔴'
            elif emoji == '🟡' and overall_status != '🔴':
                overall_status = '🟡'
        else:
            logging.warning(f"Unexpected format in Docker container status: {container}")
            continue

    embed = discord.Embed(title="Status Overview", description="\n".join(status_messages), color=discord.Color.blue())
    last_refresh = format_last_refresh()
    embed.set_footer(text=last_refresh)

    if status_message:
        dropdown = ServiceDropdown(services, docker_containers)
        view = discord.ui.View()
        view.add_item(dropdown)
        await status_message.edit(embed=embed, view=view)
        channel = status_message.channel
        await update_channel_name(channel, overall_status)

async def send_service_status(channel):
    global status_message
    services = sorted(get_enabled_services_with_user())
    docker_containers = get_docker_containers()
    if not services and not docker_containers:
        await channel.send("No services or Docker containers found.")
        return
    status_messages = []
    overall_status = '🟢'

    status_messages.append("**Service Overview**")
    for service in services[:25]:
        status, description = get_service_status_and_description(service)
        emoji = get_status_emoji(status)
        status_messages.append(f"{emoji} **{service}:** - ({description})")
        if emoji == '🔴':
            overall_status = '🔴'
        elif emoji == '🟡' and overall_status != '🔴':
            overall_status = '🟡'

    status_messages.append("\n**Docker Overview**")
    for container in docker_containers:
        split_result = container.split(": ", 1)
        if len(split_result) == 2:
            name, status = split_result
            emoji = get_docker_status_emoji(status)
            status_messages.append(f"{emoji} **Docker {name}:** - ({status})")
            if emoji == '🔴':
                overall_status = '🔴'
            elif emoji == '🟡' and overall_status != '🔴':
                overall_status = '🟡'
        else:
            logging.warning(f"Unexpected format in Docker container status: {container}")
            continue

    embed = discord.Embed(title="Status Overview", description="\n".join(status_messages), color=discord.Color.blue())
    last_refresh = format_last_refresh()
    embed.set_footer(text=last_refresh)

    dropdown = ServiceDropdown(services, docker_containers)
    view = discord.ui.View()
    view.add_item(dropdown)
    status_message = await channel.send(embed=embed, view=view)
    await update_channel_name(channel, overall_status)
    update_service_status.start()

async def update_channel_name(channel, overall_status_emoji):
    if not CHANNEL_PRECEDING_CHARACTER:
        new_name = f'{overall_status_emoji}status'
    else:
        new_name = f'{CHANNEL_PRECEDING_CHARACTER}{overall_status_emoji}status'
    if channel.name != new_name:
        await channel.edit(name=new_name)

@bot.event
async def on_ready():
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    await clear_channel(channel)
    await send_service_status(channel)
    logging.info(f'Bot logged in and monitoring services in Channel-ID {DISCORD_CHANNEL_ID}')

bot.run(DISCORD_BOT_TOKEN)
