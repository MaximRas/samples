import consts
from tools import parse_object_type


class NoLocationException(Exception):
    pass


def template_to_filter(object_type):
    attribute = parse_object_type(object_type)[1]
    filters = {}
    attribute_to_meta = {
        'bad-quality': consts.FILTER_BAD_QUALITY,
        'good-quality': consts.FILTER_GOOD_QUALITY,
        'type-minivan': consts.FILTER_MINIVAN,
        'type-sedan': consts.FILTER_SEDAN,
        'type-truck': consts.FILTER_TRUCK,
        'type-van': consts.FILTER_VAN,
        'type-wagon': consts.FILTER_WAGON,
        'type-suv': consts.FILTER_SUV,
        'type-hatchback': consts.FILTER_HATCHBACK,
        'male': consts.FILTER_MALE,
        'female': consts.FILTER_FEMALE,
    }
    if attribute:
        filters.update(attribute_to_meta[attribute])
    return filters
