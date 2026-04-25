import asyncio
import aiohttp
import ipaddress
import orjson

from http import HTTPStatus

config = orjson.loads(open('config.json', "r", encoding='utf-8').read())


def parse_ip(text: str, version: int) -> str:
    for part in text.replace("=", " ").split():
        try:
            ip = ipaddress.ip_address(part.strip())
        except ValueError:
            continue

        if ip.version == version:
            return str(ip)

    raise ValueError(f"IPv{version} provider did not return an IP")


async def get_ip(version: int) -> str | None:
    provider_key = f"ipv{version}_provider"

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=3),
            headers={"User-Agent": "curl/8.0.0"},
        ) as session:
            async with session.get(config['providers'][provider_key]) as res:
                if not HTTPStatus(res.status).is_success:
                    raise RuntimeError(f'IPv{version} provider return error')
                return parse_ip(await res.text(), version)
    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError, ValueError, RuntimeError):
        return None

 
def records_list(*ips: str) -> list:
    records: list = []
    records_by_type = {}

    for ip in ips:
        ip_version = ipaddress.ip_address(ip).version

        if ip_version == 4:
            if not config.get("a", True):
                continue
            record_type = "A"
        else:
            if not config.get("aaaa", True):
                continue
            record_type = "AAAA"

        records_by_type[record_type] = ip

    for subdomain in config['desec']['subdomain']:
        for record_type, ip in records_by_type.items():
            records.append({
                "subname": subdomain,
                "type": record_type,
                "records": [ip],
                "ttl": config['ttl'],
            })

    return records


async def update_records(records: list) -> bool:
    if not records:
        return False

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=3),
    ) as session:
        async with session.put(
            f"https://desec.io/api/v1/domains/{config['desec']['auth']['domain']}/rrsets/",
            headers={
                "Authorization": f"Token {config['desec']['auth']['api_token']}",
                "Content-Type": "application/json"
            },
            json=records
        ) as res:
            if not HTTPStatus(res.status).is_success:
                return False
            return True


async def main() -> None:
    tasks = []

    if config.get("a", True):
        tasks.append(get_ip(4))
    if config.get("aaaa", True):
        tasks.append(get_ip(6))

    ips = await asyncio.gather(*tasks)
    records = records_list(*(ip for ip in ips if ip))

    while True:
        await update_records(records)
        asyncio.sleep(30 * 60)


if __name__ == "__main__":
    asyncio.run(main())
