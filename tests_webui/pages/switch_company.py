from copy import deepcopy
from typing import Any
from typing import Mapping
from typing import Sequence
import logging
import time

import allure

import consts
from tools.retry import retry
from tools.types import IcoType
from tools.types import XPathType
from tools.types import CompanyNameType
from tools.users import get_company_by_name
from tools.users import set_active_company
from tools.webdriver import WebElement
from tools.webdriver import find_element
from tools.webdriver import find_elements

from pages.base_page import BasePage
from pages.dialog import Dialog
from pages.input_field import SearchInput

log = logging.getLogger(__name__)

CURRENT_COMPANY = 'Current company'
FAVORITE_COMPANIES = 'Favorite Companies'
RECENTLY_VISITED_COMPANIES = 'Recently Visited Companies'
AVAILABLE_COMPANIES = 'Available companies'
MARKED_FOR_DELETION = 'Companies marked for deletion'
COMPANY_GROUPS = (
    CURRENT_COMPANY,
    FAVORITE_COMPANIES,
    RECENTLY_VISITED_COMPANIES,
    AVAILABLE_COMPANIES,
    MARKED_FOR_DELETION,
)
ICO_STAR = IcoType('M339.923-267.308 480-352.077l140.077 85.769-36.615-160.307 123.384-106.924L544.077-548 480-698.308 415.923-549l-162.769 14.461 123.384 107.693-36.615 159.538ZM293-203.076l49.615-212.539-164.923-142.847 217.231-18.846L480-777.693l85.077 200.385 217.231 18.846-164.923 142.847L667-203.076 480-315.923 293-203.076Zm187-269.616Z')
ICO_WHITE_STAR = IcoType('m293-203.076 49.615-212.539-164.923-142.847 217.231-18.846L480-777.693l85.077 200.385 217.231 18.846-164.923 142.847L667-203.076 480-315.923 293-203.076Z')
CompanySchemaType = Mapping[str, Sequence | str]


class NoCompanyNameException(Exception):
    pass


def merge_recently_visited_and_favorite(schema: dict[str, Any]) -> CompanySchemaType:
    schema = deepcopy(schema)
    recently_and_visited = []
    recently_and_visited.extend(schema.pop(AVAILABLE_COMPANIES, []))  # type: ignore (Expected 1 positional argument (reportCallIssue))
    recently_and_visited.extend(schema.pop(RECENTLY_VISITED_COMPANIES, []))  # type: ignore (Expected 1 positional argument (reportCallIssue))
    return {'Available / Recently Visited Companies': recently_and_visited}


def move_group_to_favorites(schema: dict[str, Any], group_title: str, company_name: str) -> CompanySchemaType:
    '''
    Changes source `schema`: remove `company_name` from `group_title` and add `company_name` to "favorite groups"
    '''
    schema = deepcopy(schema)
    schema[group_title].remove(company_name)
    if not schema[group_title]:
        del schema[group_title]
    if FAVORITE_COMPANIES not in schema:
        schema[FAVORITE_COMPANIES] = []
    schema[FAVORITE_COMPANIES].append(f'{company_name} ★')
    return merge_recently_visited_and_favorite(schema)


class Company:
    def __init__(self, element: WebElement):
        self._element = element

    def __str__(self) -> str:
        return self.name

    @property
    def _star(self) -> WebElement:
        elements = find_elements(
            self._element,
            XPathType(".//div[@class='Tooltip' and @data-state]"),
        )
        if len(elements) != 1:
            raise RuntimeError
        return elements[0]

    def is_favorite(self) -> bool:
        path_element = find_element(self._star, XPathType(".//*[name()='path']"))
        ico = path_element.get_attribute('d')
        if ico == ICO_STAR:
            return False
        if ico == ICO_WHITE_STAR:
            return True
        raise RuntimeError('Unexpected behavior')

    def _get_name_element(self) -> WebElement:
        return find_element(self._element, XPathType(".//div[@class='UIItemHeader']/span"))

    @property
    def name(self) -> CompanyNameType:
        element = self._get_name_element()
        if not element.text:
            raise NoCompanyNameException
        return CompanyNameType(element.text)

    @property
    def highlighted_name(self) -> CompanyNameType:
        '''
        Highlighted element looks like:
        <span class="UIHighLight"><b>Test</b> Company izaQzu</span>
        '''
        element = find_element(self._get_name_element(), XPathType("./b"))
        return CompanyNameType(element.text)

    def click(self) -> None:
        self._element.click()

    def make_favorite(self) -> None:
        with allure.step(f'Make "{self}" favorite'):
            log.info(f'Make "{self}" favorite')
            if self.is_favorite():
                raise RuntimeError(f'{self} is favorite')
            self._star.click()
            time.sleep(1.5)

    def cancel_favorite(self) -> None:
        with allure.step(f'Remove "{self}" from favorites'):
            log.info(f'Remove "{self}" from favorites')
            if not self.is_favorite():
                raise RuntimeError(f'{self} is not favorite')
            self._star.click()
            time.sleep(1.5)


def _choose_company(company: Company, page: BasePage) -> None:
    company_name = company.name
    company.click()
    set_active_company(
        page.driver.client,
        get_company_by_name(page.driver.client, company_name),
    )
    page.wait_disappeared(timeout=20)  # "Switch System" dialog disappears after loader had disappeared
    page.wait_spinner_disappeared()


class SwitchSystemDialog(Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            title="Choose company",
            has_close_icon=True,
            check_primary_element_timeout=20,  # response which contains deleted companies may have a lot of entries
            is_mui=False,
            **kwargs,
        )
        self.wait_spinner_disappeared()  # Wait unless 'Loading companies' spinner disappeared
        self._ico_close = consts.ICO_CLOSE1

    def _parse_companies(self) -> CompanySchemaType:
        headers = self.bs4.find_all('div', class_='UISubHeader')
        schema = {}
        for header in headers:
            title = header.text
            if title not in COMPANY_GROUPS:
                raise RuntimeError(f'Unknown company group: "{title}"')
            if title == CURRENT_COMPANY:
                element = self.get_desc_obj(XPathType("//div[contains(@class, 'UIItemSelected')]"))
                schema[CURRENT_COMPANY] = Company(element)
                log.info(f'Found current company {schema[CURRENT_COMPANY]}')
                continue
            log.info(f'Looking for companies in "{title}"')
            schema[title] = []
            xpath = XPathType(self.x_root + f"//div[text()='{header.text}']/following-sibling::div[@class='UIList'][1]//div[@class='UICompanyListItem']")
            for element in self.get_objects(xpath):
                company = Company(element)
                log.info(f' -> Found {company}')
                schema[title].append(company)
        return schema

    def _get_schema(self, name_attrib: str = 'name') -> CompanySchemaType:
        log.info('Getting schema of companies')

        def pp(company):
            result = getattr(company, name_attrib)
            if company.is_favorite():
                result += ' ★'
            return result

        result = {}
        for title, companies in self._parse_companies().items():
            if isinstance(companies, Company):
                result[title] = pp(companies)
            if isinstance(companies, (list, tuple)):
                result[title] = []
                for company in companies:
                    result[title].append(pp(company))
        return result

    @property
    def schema_hightlighted(self) -> CompanySchemaType:
        return self._get_schema(name_attrib='highlighted_name')

    @property
    def schema(self) -> CompanySchemaType:
        return self._get_schema()

    @property
    def available_companies(self) -> Sequence[Company]:
        ''' List of companies except "Current company" '''
        log.info('Getting available companies')
        result = []
        schema = self._parse_companies()
        for title in schema:
            # Do not include companies marked for deletion to keep backward compatibility
            if title not in (CURRENT_COMPANY, MARKED_FOR_DELETION):
                result.extend(schema[title])
        return result

    def get_company(self, name: CompanyNameType) -> tuple[CompanyNameType, Company]:
        log.info(f'Look for company "{name}"')
        for title, companies in self._parse_companies().items():
            if isinstance(companies, Company):
                if companies.name == name:
                    return title, companies
            if isinstance(companies, (list, tuple)):
                for company in companies:
                    if company.name == name:
                        return title, company
        raise RuntimeError(f'No company with name: "{name}"')

    @property
    def _search_input(self) -> SearchInput:
        return SearchInput(
            x_root=self.x_root,
            label="Search",
            driver=self._driver,
        )

    def search_name(self, name: CompanyNameType) -> Sequence[CompanyNameType]:
        # TODO: replace to search + schema ???
        return [company.name for company in self.search(name)]

    def search(self, name: CompanyNameType) -> Sequence[Company]:
        with allure.step(f'Search company: {name}'):
            log.info(f'Search company: {name}')
            self._search_input.type_text(name, clear_with_keyboard=True)
            time.sleep(2)
            return self.available_companies

    @retry(NoCompanyNameException)
    def select_by_name(self, name: CompanyNameType) -> None:
        with allure.step(f'Select company "{name}"'):
            time.sleep(3)  # do not click at company name too fast
            log.info(f'Select company "{name}"')
            for company in self.available_companies:
                log.debug(f'Check "{company.name}" vs "{name}"')
                if company.name == name:
                    _choose_company(company, self)
                    return
            raise RuntimeError(f'No company with name: "{name}"')

    def select_by_index(self, ix: int) -> None:
        with allure.step(f'Select company #{ix}'):
            time.sleep(3)  # do not click at company name too fast
            log.info(f'Select company #{ix}')
            company = self.available_companies[ix]
            _choose_company(company, self)
