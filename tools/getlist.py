from typing import List
from typing import TypeVar
import logging

from tools import UndefinedElementException
from tools import NoDataFoundException

log = logging.getLogger(__name__)
T = TypeVar('T')


class GetList(List[T]):
    def get_first(self) -> T:
        if len(self) < 1:
            raise NoDataFoundException
        entity = self[0]
        log.info(f'GetList.get_first: return {entity}')
        return entity

    def get(self, name: str, exception=NoDataFoundException) -> T:
        if len(self) < 1:
            raise exception('List is empty')

        childs = [c for c in self if c.name == name]
        if not childs:
            raise exception(f'GetList.get: there is no {name}')
        if len(childs) != 1:
            raise UndefinedElementException(f'Several entities with name "{name}"')
        entity = childs[0]
        log.info(f'GetList.get: return {entity}')
        return entity
