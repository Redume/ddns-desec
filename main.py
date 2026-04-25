import asyncio
import aiohttp
import ipaddress
import orjson
import logging

from http import HTTPStatus

config = orjson.loads(open('config.json', "r", encoding='utf-8').read())
logging.basicConfig(
    level=config['log_level'].upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)

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

                ip = parse_ip(await res.text(), version)
                logging.debug(f"IPv{version} return {ip}")
                return ip

    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError, ValueError, RuntimeError):
        logging.error(f"IPv{version} wasn't able to get")
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
        if subdomain == "@":
            subdomain = ""

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
        logging.info("subdomain is empty, skipping")
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
                logger.error(await res.text())
                return False

            logging.info("Records is successfuly updated")
            return True


async def main() -> None:
    logging.info("ddns started")
    tasks = []

    if config.get("a", True):
        tasks.append(get_ip(4))
    if config.get("aaaa", True):
        tasks.append(get_ip(6))

    ips = await asyncio.gather(*tasks)

    while True:
        records = records_list(*(ip for ip in ips if ip))
        await update_records(records)
        await asyncio.sleep(config['update_min'] * 60)


if __name__ == "__main__":
    asyncio.run(main())
