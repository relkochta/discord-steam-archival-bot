import hashlib
from mimetypes import guess_extension
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse


import aiohttp
import discord


STEAM_CDN_DOMAIN = "cdn.steamusercontent.com"


def sha256sum(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


async def download_to_file(name: str, url: str, dir: Path) -> Path:
    """
    Downloads from a URL into the directory.
    Returns the path of the downloaded file (which will include an extension).
    If the file already exists, it is *not* overwritten.
    """
    CHUNK_SIZE = 8192

    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.get(url) as stream:
            extension = guess_extension(stream.content_type)

            output_path = (dir / name).with_suffix(extension)
            if output_path.is_file():
                print(f"File {output_path} already exists!")
            else:
                print(f"Downloading {output_path} from {url}")

                with output_path.open("wb") as f:
                    async for chunk in stream.content.iter_chunked(CHUNK_SIZE):
                        f.write(chunk)

                print(" -> download complete!")

            return output_path


class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

    async def on_message(self, message: discord.Message):
        for embed in message.embeds:
            # Is this embed a video?
            if embed.type != "video":
                continue

            # Is this embed a Steam clip?
            url = embed.url
            parsed_url = urlparse(url)
            proxy_url = embed.video.proxy_url
            if parsed_url.netloc != STEAM_CDN_DOMAIN:
                continue

            # If so, download and save the clip
            hash = sha256sum(url)
            output_path = await download_to_file(hash, proxy_url, SERV_DIR)

            # Construct the externally-reachable video URL
            result_url = urljoin(BASE_URL, output_path.name)
            await message.reply(
                f"Steam clip archived! [Link]({result_url})",
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, users=False, roles=False, replied_user=False
                ),
            )


def main():
    # Setup
    global BASE_URL, SERV_DIR
    BASE_URL = os.getenv("BASE_URL")
    SERV_DIR = os.getenv("SERV_DIR")
    bot_token = os.getenv("BOT_TOKEN")

    assert (
        BASE_URL is not None and SERV_DIR is not None and bot_token is not None
    ), "Required environment variables were missing"

    SERV_DIR = Path(SERV_DIR)
    SERV_DIR.mkdir(exist_ok=True)

    intents = discord.Intents.default()
    intents.message_content = True

    client = MyClient(intents=intents)
    client.run(bot_token)


if __name__ == "__main__":
    main()
