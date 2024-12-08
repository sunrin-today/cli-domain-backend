from json import loads


class LocalDBService:
    def __init__(self) -> None:
        self._domain_db = loads(open("domain.json").read())

    async def available_domains(self) -> list[str]:
        return list(self._domain_db["domains"].keys())

    async def get_zone_id(self, domain: str) -> str:
        return self._domain_db["domains"][domain]["zone_id"]
