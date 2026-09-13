import asyncio


async def handle_client(reader, writer):
    address = writer.get_extra_info("peername")

    print(f"Client connected: {address}")

    while True:
        data = await reader.read(1024)

        if not data:
            break

        print(f"Received: {data}")

        writer.write(data)
        await writer.drain()

    print(f"Client disconnected: {address}")

    writer.close()
    await writer.wait_closed()


async def main():
    server = await asyncio.start_server(
        handle_client,
        "127.0.0.1",
        8080
    )

    address = server.sockets[0].getsockname()

    print(f"Server running on {address}")

    async with server:
        await server.serve_forever()


asyncio.run(main())