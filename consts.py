from pathlib import Path
from typing import TYPE_CHECKING

from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from tools.types import IcoType
    from tools.types import TimesliceType
else:
    IcoType = str
    TimesliceType = str

DEFAULT_CONFIG = 'config.yaml'

LOG_DIR = Path('logs/')

ENV_PRODS = ('sharpvue', 'mymetapix', 'mydw')

WIDGET_VALUE = 'value'
WIDGET_LIVE_FEED = 'live_feed'
WIDGET_PIE_CHART = 'pie_chart'
WIDGET_LINE_CHART = 'line_chart'
WIDGET_BAR_LINE_CHART = 'bar_line_chart'
WIDGET_BAR_CHART = 'bar_chart'

WIDGET_ALL_CHARTS = (WIDGET_VALUE, WIDGET_PIE_CHART, WIDGET_BAR_CHART, WIDGET_LINE_CHART)
WIDGET_ALL_TYPES = WIDGET_ALL_CHARTS + (WIDGET_LIVE_FEED, )

BASE_FACE = 'face'
BASE_VEHICLE = 'vehicle'
BASE_PERSON = 'person'

BASES_WITH_CLUSTERS = (BASE_FACE, )
BASES_ALL = (BASE_FACE, BASE_VEHICLE, BASE_PERSON)

# Microservices:
SERVICE_AUTH_MANAGER = 'auth-manager'
SERVICE_DEVICE_MANAGER = 'device-manager'
SERVICE_OBJECT_MANAGER = 'object-manager'
SERVICE_LAYOUT_MANAGER = 'layout-manager'
SERVICE_CHART_MANAGER = 'chartilla'
SERVICE_STATS_MANAGER = 'stats'
SERVICE_NOTIFICATION_MANAGER = 'notifications'
SERVICE_META_RECEIVER = 'meta-receiver'
SERVICE_WATCHLIST_MANAGER = 'notification-manager'

AUTOREFRESH_TIME = 30

# Values for builder filters
OPTION_ALL = "All"
OPTION_ALL_VEHICLE_TYPES = 'All'
OPTION_ALL_GENDERS = 'All'
OPTION_ALL_IMAGE_QUALITY = 'All'
OPTION_WITH = "With"
OPTION_WITHOUT = "Without"
OPTION_TRUE = "True"
OPTION_FALSE = "False"
SOURCE_IMG_QUALITY_BAD = "Bad"
SOURCE_IMG_QUALITY_GOOD = "Good"
GENDER_FEMALE = "Female"
GENDER_MALE = "Male"
VEHICLE_TYPE_SEDAN = "Sedan"
VEHICLE_TYPE_SUV = "SUV"
VEHICLE_TYPE_VAN = "Van"

# UI search filter fields
FILTER_TITLE = "Widget title"  # not a filter actually...
FILTER_SEARCH_OBJECTIVE = 'Search objective'
FILTER_BASE = "Select base"
FILTER_GENDER = "Gender"
FILTER_OBJECTS_NAME = "Cluster's name"
FILTER_OBJECTS_NOTES = "Object's details"
FILTER_IMAGE_QUALITY = "Source image quality"
FILTER_VEHICLE_TYPE = "Vehicle type"
FILTER_LICENSE_PLATE = "Vehicle license plate"
FILTER_AGE = "Age"
FILTER_ORDER_BY = "Order results by"
FILTER_CAMERAS_LOCATIONS = "Cameras / Locations"
FILTER_START_PERIOD = "Start Period"
FILTER_END_PERIOD = "End Period"
FILTER_OBJECT_TYPE = 'Object Type'
FILTER_WATCHLIST_NAME = 'Watch List Name'
FILTER_OBJECT_ID = 'Object Identifier'
SEARCH_OBJECTIVE_ID = 'Identification Number'

RESOLUTION = (1920, 1080)  # TODO: move to config.yaml

DETS_IN_SECONDS = {
    '5m': 60 * 5,
    '10m': 60 * 10,
    '30m': 60 * 30,
    '1h': 60 * 60,
    '2h': 2 * 60 * 60,
    '4h': 4 * 60 * 60,
    '6h': 6 * 60 * 60,
    '12h': 60 * 60 * 12,
    '1d': 60 * 60 * 24,
    '2d': 60 * 60 * 24 * 2,
}

TIMESLICES_IN_SECONDS = {
    '1h': 60 * 60,
    '6h': 60 * 60 * 6,
    '12h': 60 * 60 * 12,
    '1d': 60 * 60 * 24,
    '3d': 60 * 60 * 24 * 3,
    '1w': 60 * 60 * 24 * 7,
    '2w': 60 * 60 * 24 * 14,
}

TIMESLICE_DETAILS = {
    '1h': ['5m', '10m'],
    '6h': ['30m', '1h'],
    '12h': ['1h', '2h'],
    '1d': ['2h', '4h'],
    '3d': ['6h', '12h'],
    '1w': ['12h', '1d'],
    '2w': ['1d', '2d'],
}

DEFAULT_TIMESLICE = TimesliceType('12h')

tz_pst = ZoneInfo('US/Pacific')
tz_msk = ZoneInfo('Europe/Moscow')

FACE_GENDERS = (
    "face-male",
    "face-female",
)

VEHICLE_TYPE_TEMPLATES = (
    "vehicle-type-minivan",
    "vehicle-type-truck",
    "vehicle-type-van",
    "vehicle-type-wagon",
    "vehicle-type-sedan",
    "vehicle-type-hatchback",
    'vehicle-type-suv',
    "vehicle-type-unknown",
)

COLOR_DISABLED_BUTTON = 'rgba(115, 115, 115, 1)'
BLUE_THEME_BUTTON_ACTIVE = 'rgba(11, 146, 183, 1)'
BLUE_THEME_BUTTON_ACTIVE_PRESSED = 'rgba(7, 102, 128, 1)'
BLUE_THEME_BUTTON_INACTIVE = 'rgba(47, 49, 51, 1)'
BLUE_THEME_BUTTON_INACTIVE_PRESSED = 'rgba(32, 34, 35, 1)'
SHARPVUE_THEME_BUTTON_ACTIVE = 'rgba(253, 102, 0, 1)'
SHARPVUE_THEME_BUTTON_ACTIVE_PRESSED = 'rgba(177, 71, 0, 1)'
ORANGE_THEME_BUTTON_ACTIVE = 'rgba(255, 108, 0, 1)'
ORANGE_THEME_BUTTON_ACTIVE_PRESSED = 'rgba(178, 75, 0, 1)'
ORANGE_THEME_BUTTON_INACTIVE = 'rgba(48, 48, 48, 1)'

COLOR_WHITE = 'rgba(255, 255, 255, 1)'
BUTTON_BLACK_INACTIVE = 'rgba(0, 0, 0, 0)'

META_LIC_PLATE = 'license_plate'
AGE_RANGE_STUB = '_age_range'  # custom meta key. do not send it to backend
META_IS_REF = {"is_reference": True}
META_ISNT_REF = {"is_reference": False}
META_IS_MATCH = {"matched": True}
META_ISNT_MATCH = {"matched": False}
META_ANY_QUALITY = {"_any_quality_stub": True}
META_BAD_QUALITY = {"bad_quality": "bad"}
META_GOOD_QUALITY = {"bad_quality": "good"}
META_WITH_GLASSES = {"glasses": "with"}
META_WITHOUT_GLASSES = {"glasses": "without"}
META_WITH_MASK = {"mask": "with"}
META_WITHOUT_MASK = {"mask": "without"}
META_WITH_BEARD = {"beard": "with"}
META_WITHOUT_BEARD = {"beard": "without"}
META_WHITE = {"color": "white"}
META_BLACK = {"color": "black"}
META_BLUE = {"color": "blue"}
META_MODEL_X5_SUV = {"model": "x5 suv"}
META_MALE = {"gender": "male"}
META_FEMALE = {"gender": "female"}
META_MINIVAN = {"type": "minivan"}
META_SUV = {"type": "suv"}
META_UNKNOWN_VEHICLE = {"type": None}
META_SEDAN = {"type": "sedan"}
META_TRUCK = {"type": "truck"}
META_WAGON = {"type": "wagon"}
META_VAN = {"type": "van"}
META_HATCHBACK = {"type": "hatchback"}
META_LIC_PLATE_12345 = {META_LIC_PLATE: '12345'}
META_LIC_PLATE_ANY = {META_LIC_PLATE: '*'}
META_NISSAN = {"manufacturer": "nissan"}

INVALID_PASSWORD = "string"

DEFAULT_PGSIZE = 32
MAX_LIVE_FEED_RESULTS = 32

ORDER_NEW_TO_OLD = "New To Old"
ORDER_OLD_TO_NEW = "Old To New"

# common
FILTER_ANY_QUALITY = {FILTER_IMAGE_QUALITY: OPTION_ALL_IMAGE_QUALITY}
FILTER_GOOD_QUALITY = {FILTER_IMAGE_QUALITY: SOURCE_IMG_QUALITY_GOOD}
FILTER_BAD_QUALITY = {FILTER_IMAGE_QUALITY: SOURCE_IMG_QUALITY_BAD}
FILTER_ORDER_BY_OLD_TO_NEW = {FILTER_ORDER_BY: ORDER_OLD_TO_NEW}
FILTER_ORDER_BY_NEW_TO_OLD = {FILTER_ORDER_BY: ORDER_NEW_TO_OLD}  # default sort method
FILTER_VEHICLE = {FILTER_OBJECT_TYPE: 'Vehicle'}
FILTER_FACE = {FILTER_OBJECT_TYPE: 'Face'}

# face
FILTER_MALE = {FILTER_GENDER: GENDER_MALE}
FILTER_FEMALE = {FILTER_GENDER: GENDER_FEMALE}
FILTER_ANY_GENDER = {FILTER_GENDER: OPTION_ALL_GENDERS}

# vehicle
FILTER_ANY_VEHICLE = {FILTER_VEHICLE_TYPE: OPTION_ALL_VEHICLE_TYPES}
FILTER_SEDAN = {FILTER_VEHICLE_TYPE: VEHICLE_TYPE_SEDAN}
FILTER_MINIVAN = {FILTER_VEHICLE_TYPE: "Minivan"}
FILTER_SEDAN = {FILTER_VEHICLE_TYPE: "Sedan"}
FILTER_SUV = {FILTER_VEHICLE_TYPE: VEHICLE_TYPE_SUV}
FILTER_HATCHBACK = {FILTER_VEHICLE_TYPE: 'Hatchback'}
FILTER_TRUCK = {FILTER_VEHICLE_TYPE: "Truck"}
FILTER_VAN = {FILTER_VEHICLE_TYPE: VEHICLE_TYPE_VAN}
FILTER_WAGON = {FILTER_VEHICLE_TYPE: 'Wagon'}

ICO_RIGHT_ARROW = IcoType('m312.461-108.923-36-35.462 336.847-336.846-336.847-336.077 36-36.231 372.308 372.308-372.308 372.308Z')
ICO_SQUARE = IcoType('M215.384-160q-23.057 0-39.221-16.163Q160-192.327 160-215.384v-141.231h30.769v141.231q0 9.23 7.692 16.923 7.693 7.692 16.923 7.692h141.231V-160H215.384Zm388.001 0v-30.769h141.231q9.23 0 16.923-7.692 7.692-7.693 7.692-16.923v-141.231H800v141.231q0 23.057-16.163 39.221Q767.673-160 744.616-160H603.385ZM160-603.385v-141.231q0-23.057 16.163-39.221Q192.327-800 215.384-800h141.231v30.769H215.384q-9.23 0-16.923 7.692-7.692 7.693-7.692 16.923v141.231H160Zm609.231 0v-141.231q0-9.23-7.692-16.923-7.693-7.692-16.923-7.692H603.385V-800h141.231q23.057 0 39.221 16.163Q800-767.673 800-744.616v141.231h-30.769Z')
ICO_HIDE_OBJECT_INFO = IcoType('M215.384-160q-22.442 0-38.913-16.471Q160-192.942 160-215.384v-529.232q0-22.442 16.471-38.913Q192.942-800 215.384-800h529.232q22.442 0 38.913 16.471Q800-767.058 800-744.616v529.232q0 22.442-16.471 38.913Q767.058-160 744.616-160H215.384Zm0-30.769h529.232q10.769 0 17.692-6.923t6.923-17.692v-473.847H190.769v473.847q0 10.769 6.923 17.692t17.692 6.923ZM280-504.615v-30.77h395.385v30.77H280Zm0 160v-30.77h235.385v30.77H280Z')
ICO_BUTTON_LINE_CHART = IcoType("M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z")
ICO_BUTTON_BAR_CHART = IcoType("M5 9.2h3V19H5zM10.6 5h2.8v14h-2.8zm5.6 8H19v6h-2.8z")
ICO_ZOOM_OUT = IcoType('M785.231-154.077 529.154-410.154q-29.696 26.829-69.261 40.914-39.564 14.086-79.585 14.086-95.585 0-161.793-66.028-66.208-66.029-66.208-161.001 0-94.971 66.029-161.125t160.941-66.154q94.911 0 161.509 66.065 66.599 66.066 66.599 160.961 0 41.205-14.769 80.821-14.77 39.615-41.231 69.23l256.308 255.077-22.462 23.231ZM380.077-385.923q82.66 0 139.599-56.731 56.939-56.731 56.939-139.654t-56.939-139.654q-56.939-56.73-139.599-56.73-82.853 0-139.926 56.73-57.074 56.731-57.074 139.654t57.074 139.654q57.073 56.731 139.926 56.731Zm-91.231-181.615v-30.77h181.769v30.77H288.846Z')
ICO_ZOOM_IN = IcoType('M785.231-154.077 529.154-410.154q-29.696 26.829-69.261 40.914-39.564 14.086-79.585 14.086-95.585 0-161.793-66.028-66.208-66.029-66.208-161.001 0-94.971 66.029-161.125t160.941-66.154q94.911 0 161.509 66.065 66.599 66.066 66.599 160.961 0 41.205-14.769 80.821-14.77 39.615-41.231 69.23l256.308 255.077-22.462 23.231ZM380.077-385.923q82.66 0 139.599-56.731 56.939-56.731 56.939-139.654t-56.939-139.654q-56.939-56.73-139.599-56.73-82.853 0-139.926 56.73-57.074 56.731-57.074 139.654t57.074 139.654q57.073 56.731 139.926 56.731Zm-15.616-105v-76.615h-76.615v-30.77h76.615v-75.615h30.77v75.615h75.615v30.77h-75.615v76.615h-30.77Z')
ICO_EXPAND_ARROW_DOWN = IcoType('M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z')
ICO_COLLAPSE_ARROW_UP = IcoType('M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z')
ICO_CLOSE0 = IcoType('M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z')
ICO_LEFT_ARROW = IcoType('M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z')
ICO_EXPAND_MENU = IcoType('M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z')
ICO_COLLAPSE_BUTTON = IcoType('M12 8l-6 6 1.41 1.41L12 10.83l4.59 4.58L18 14z')
ICO_HIDE_PANEL = IcoType('M625.308-364v-232L508.539-480l116.769 116ZM215.384-160q-22.442 0-38.913-16.471Q160-192.942 160-215.384v-529.232q0-22.442 16.471-38.913Q192.942-800 215.384-800h529.232q22.442 0 38.913 16.471Q800-767.058 800-744.616v529.232q0 22.442-16.471 38.913Q767.058-160 744.616-160H215.384Zm107.77-30.769v-578.462h-107.77q-9.23 0-16.923 7.692-7.692 7.693-7.692 16.923v529.232q0 9.23 7.692 16.923 7.693 7.692 16.923 7.692h107.77Zm30.769 0h390.693q9.23 0 16.923-7.692 7.692-7.693 7.692-16.923v-529.232q0-9.23-7.692-16.923-7.693-7.692-16.923-7.692H353.923v578.462Zm-30.769 0H190.769h132.385Z')
ICO_SHOW_PANEL = IcoType('M508.539-596v232l116.769-116-116.769-116ZM215.384-160q-22.442 0-38.913-16.471Q160-192.942 160-215.384v-529.232q0-22.442 16.471-38.913Q192.942-800 215.384-800h529.232q22.442 0 38.913 16.471Q800-767.058 800-744.616v529.232q0 22.442-16.471 38.913Q767.058-160 744.616-160H215.384Zm107.77-30.769v-578.462h-107.77q-9.23 0-16.923 7.692-7.692 7.693-7.692 16.923v529.232q0 9.23 7.692 16.923 7.693 7.692 16.923 7.692h107.77Zm30.769 0h390.693q9.23 0 16.923-7.692 7.692-7.693 7.692-16.923v-529.232q0-9.23-7.692-16.923-7.693-7.692-16.923-7.692H353.923v578.462Zm-30.769 0H190.769h132.385Z')
ICO_CLOSE1 = IcoType('m252.846-230.846-22-22L458-480 230.846-707.154l22-22L480-502l227.154-227.154 22 22L502-480l227.154 227.154-22 22L480-458 252.846-230.846Z')

API_LIC_PLATE = 'vehicle_license_plate'
API_ORDER_DATE = {"timestamp": "timestamp"}
API_ORDER_DATE_DESC = {"timestamp": "timestamp desc"}
API_ORDER_CLUSTER_SIZE = {"cluster_size": "cluster_size"}
API_ORDER_CLUSTER_SIZE_DESC = {"cluster_size": "cluster_size desc"}
API_REFS_ALL = {}
API_REFS_ONLY = {'is_reference': 'True'}
API_NOT_REFS = {'is_reference': 'False'}
API_ANY_NOTES = {'notes': '*'}
API_ANY_NAME = {'name': '*'}
API_MALE = {'face_gender': 1}
API_FEMALE = {'face_gender': 0}
API_MASK = {'face_mask': 1}
API_BEARD = {'face_beard': 1}
API_GLASSES = {'face_glasses': 1}
API_GOOD_QUALITY = {'image_quality': 0}
API_ANY_QUALITY = {'image_quality': 'all'}  # FYI: stub to make any quality explicit. will be removed before send request
API_BAD_QUALITY = {'image_quality': 1}
API_SUV = {'vehicle_type': 'SUV'}
API_YELLOW = {'vehicle_color': ['yellow']}
API_WHITE = {'vehicle_color': ['white']}
API_BLACK = {'vehicle_color': ['black']}
API_SEDAN = {'vehicle_type': ['Sedan']}
API_WAGON = {'vehicle_type': ['Wagon']}
API_MINIVAN = {'vehicle_type': ['Minivan']}
API_TRUCK = {'vehicle_type': ['Truck']}
API_HATCHBACK = {'vehicle_type': ['Hatchback']}
API_NISSAN = {'vehicle_manufacturer': ['Nissan']}


PAGINATION_MAX = 200

MIN_OFFSET_TO_MOVE_WIDGET = 250

HOUR_SECONDS = 60 * 60
DAY_SECONDS = HOUR_SECONDS * 24
