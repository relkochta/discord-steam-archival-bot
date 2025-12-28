import hashlib
from mimetypes import guess_extension
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse


import aiohttp
import aiosqlite
import discord


REACT_EMOJI = "\N{FILE CABINET}"
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


async def db_insert_reply(cursor: aiosqlite.Cursor, message_id: int, reply_id: int):
    await cursor.execute(
        "INSERT INTO replies VALUES(?, ?)", (str(message_id), str(reply_id))
    )


async def db_fetch_reply(cursor: aiosqlite.Cursor, message_id: int) -> Optional[int]:
    query_res = await cursor.execute(
        "SELECT message_id, reply_id FROM replies WHERE message_id = ?;",
        (str(message_id),),
    )
    result = await query_res.fetchone()
    if result is None:
        return None

    (_, reply_id) = result

    return int(reply_id)


async def db_delete_reply(cursor: aiosqlite.Cursor, message_id: int):
    await cursor.execute(
        "DELETE FROM replies WHERE message_id = ?;", (str(message_id),)
    )


class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

        self.sqlite_connection = aiosqlite.connect(SQLITE_DB_URL)
        await self.sqlite_connection.__aenter__()

        async with self.sqlite_connection.cursor() as cur:
            # Use TEXT instead of 64-bit integers since SQLite doesn't
            # support 64-bit unsigned integers
            await cur.execute(
                """CREATE TABLE replies (
                    message_id TEXT PRIMARY KEY,
                    reply_id TEXT
                ) WITHOUT ROWID;
                """
            )

    async def close(self):
        # Close the SQLite connection
        await self.sqlite_connection.__aexit__(None, None, None)

        await super().close()

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

            # Share the archived video in the chat
            await message.add_reaction(REACT_EMOJI)
            reply = await message.reply(
                f"Steam clip archived! [Link]({result_url})",
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, users=False, roles=False, replied_user=False
                ),
            )

            # Save the reply id in our database (for deletions)
            async with self.sqlite_connection.cursor() as cur:
                await db_insert_reply(cur, message.id, reply.id)

    async def on_raw_message_delete(self, event: discord.RawMessageDeleteEvent):
        # We can shortcut checks if we haven't reacted to the message
        if event.cached_message is not None:
            reacts = event.cached_message.reactions
            was_archived = any(
                map(lambda react: react.emoji == REACT_EMOJI and react.me, reacts)
            )
            if not was_archived:
                return

        message_id = event.message_id

        async with self.sqlite_connection.cursor() as cur:
            reply_id = await db_fetch_reply(cur, message_id)

        # If we don't remember a reply do this message, ignore
        if reply_id is None:
            print(
                "WARNING: Archived message deleted, but no record of reply found in database"
            )
            return

        print(f"Deleting message with id={reply_id}")

        # Fetch the message
        channel = self.get_channel(event.channel_id)
        reply_message = await channel.fetch_message(reply_id)

        # Delete it (after sanity check to make sure we don't delete another user's message)
        assert (
            reply_message.author == self.user
        ), "Was about to delete another user's message!"
        await reply_message.delete()
        async with self.sqlite_connection.cursor() as cur:
            await db_delete_reply(cur, message_id)


def main():
    # Setup
    global BASE_URL, SERV_DIR, SQLITE_DB_URL
    BASE_URL = os.getenv("BASE_URL")
    SERV_DIR = os.getenv("SERV_DIR")
    SQLITE_DB_URL = os.getenv("SQLITE_DB_URL")
    bot_token = os.getenv("BOT_TOKEN")

    assert all(
        map(lambda v: v is not None, [BASE_URL, SERV_DIR, SQLITE_DB_URL, bot_token])
    ), "At least one required environment variable was missing"

    SERV_DIR = Path(SERV_DIR)
    SERV_DIR.mkdir(exist_ok=True)

    intents = discord.Intents.default()
    intents.message_content = True

    client = MyClient(intents=intents)
    client.run(bot_token)


if __name__ == "__main__":
    main()
