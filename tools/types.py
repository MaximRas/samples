from typing import NewType
from typing import Literal
from typing import MutableMapping
from typing import Any

from strenum import StrEnum


ApiUserRole = StrEnum('ApiUserRole', ['admin', 'regular'])
ApiCompanyType = StrEnum('ApiCompanyType', ['user', 'provider', 'integrator'])


class XPathType(str):
    def __add__(self, other):
        return self.__class__(str(self) + str(other))


DateTimeFormatType = NewType('DateTimeFormatType', str)
StrDateType = NewType('StrDateType', str)
IcoType = NewType('IcoType', str)
BaseType = Literal['face'] | Literal['vehicle'] | Literal['person']
UrlType = NewType('UrlType', str)


class EmailType(str):
    def __eq__(self, other):
        return self.lower() == other.lower()

    def __str__(self):
        return self.lower()

    def __hash__(self):
        return super().__hash__()


EnvNameType = (
    Literal['alphatest1'] |
    Literal['alphatest2'] |
    Literal['dev-dw'] |
    Literal['dev-metapix'] |
    Literal['mydw'] |
    Literal['mymetapix'] |
    Literal['sharpvue'] |
    Literal['staging']
)
FiltersType = MutableMapping[str, Any]
IdStrType = NewType('IdStrType', str)
IdIntType = NewType('IdIntType', int)
TokenType = NewType('TokenType', str)
TimestampType = NewType('TimestampType', int)
AddressType = NewType('AddressType', str)
CompanyNameType = NewType('CompanyNameType', str)
ImageTemplateType = (
    Literal['face'] |
    Literal['face-30-age'] |
    Literal['face-50-age'] |
    Literal['face-70-age'] |
    Literal['face-bad-quality'] |
    Literal['face-female'] |
    Literal['face-good-quality'] |
    Literal['face-male'] |
    Literal['face-with-beard'] |
    Literal['face-with-glasses'] |
    Literal['face-with-mask'] |
    Literal['person'] |
    Literal['person-bad-quality'] |
    Literal['person-good-quality'] |
    Literal['vehicle'] |
    Literal['vehicle-bad-quality'] |
    Literal['vehicle-color-black'] |
    Literal['vehicle-color-blue'] |
    Literal['vehicle-color-white'] |
    Literal['vehicle-good-quality'] |
    Literal['vehicle-manufacturer-nissan'] |
    Literal['vehicle-model-x5_suv'] |
    Literal['vehicle-type-hatchback'] |
    Literal['vehicle-type-minivan'] |
    Literal['vehicle-type-sedan'] |
    Literal['vehicle-type-suv'] |
    Literal['vehicle-type-truck'] |
    Literal['vehicle-type-unknown'] |
    Literal['vehicle-type-van'] |
    Literal['vehicle-type-wagon']
)
LicPlateType = NewType('LicPlateType', str)
TimesliceType = NewType('TimesliceType', str)
WidgetType = (
    Literal['bar_chart'] |
    Literal['line_chart'] |
    Literal['live_feed'] |
    Literal['pie_chart'] |
    Literal['value']
)
