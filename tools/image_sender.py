from datetime import datetime
from concurrent import futures
from functools import cached_property
from pathlib import Path
from typing import Any
from typing import Sequence
from typing import Mapping
from typing import MutableMapping
from typing import TypedDict
from typing import Optional
import io
import json
import logging
import re
import shutil
import time
import uuid

from PIL import Image, ImageDraw, ImageFile, ImageFont
from requests.exceptions import ConnectionError
from requests.exceptions import JSONDecodeError
from typing_extensions import Self
import allure
import msgpack
import pytest
import requests

import consts
from tools import ObjectData
from tools import PreconditionException
from tools import config
from tools import parse_object_type
from tools.config import get_env_data
from tools.retry import retry
from tools.cameras import CameraData
from tools.cameras import get_camera_by_id
from tools.cameras import get_camera_by_name
from tools.cameras import get_cameras
from tools.client import ApiClient
from tools.objects import get_object
from tools.search import search_api_v2
from tools.time_tools import Ago
from tools.time_tools import filter_objects_by_timeslice
from tools.time_tools import filter_objects_by_timestamps
from tools.time_tools import format_date_chart_like
from tools.time_tools import now_pst
from tools.time_tools import timestamp_to_date
from tools.types import ImageTemplateType
from tools.types import TimestampType
from tools.types import BaseType
from tools.types import IdIntType

ImageFile.LOAD_TRUNCATED_IMAGES = True

log = logging.getLogger(__name__)


class UnprocessableEntityException(Exception):
    pass


class MetaInformationException(Exception):
    pass


class ClusterizationException(Exception):
    pass


Roi = TypedDict('Roi', {'x1': float, 'x2': float, 'y1': float, 'y2': float})
BASE_TO_ID = {
    consts.BASE_FACE: 0,
    consts.BASE_VEHICLE: 1,
    consts.BASE_PERSON: 2,
}
DEFAULT_ROI = Roi({'x1': 0.05, 'y1': 0.05, 'x2': 0.95, 'y2': 0.95})
MetaType = MutableMapping[str, Any]


def parse_template(object_type: ImageTemplateType, **kwargs) -> MetaType:
    base, attribute, _ = parse_object_type(object_type)
    meta = (kwargs.pop('meta', None) or {}).copy()
    attribute_to_meta = {
        'bad-quality': consts.META_BAD_QUALITY,
        'good-quality': consts.META_GOOD_QUALITY,
        'manufacturer-nissan': consts.META_NISSAN,
        'model-x5_suv': consts.META_MODEL_X5_SUV,
        'color-white': consts.META_WHITE,
        'color-black': consts.META_BLACK,
        'color-blue': consts.META_BLUE,
        'type-minivan': consts.META_MINIVAN,
        'type-sedan': consts.META_SEDAN,
        'type-truck': consts.META_TRUCK,
        'type-van': consts.META_VAN,
        'type-wagon': consts.META_WAGON,
        'type-suv': consts.META_SUV,
        'type-unknown': consts.META_UNKNOWN_VEHICLE,
        'type-hatchback': consts.META_HATCHBACK,
        'with-glasses': consts.META_WITH_GLASSES,
        'with-beard': consts.META_WITH_BEARD,
        'with-mask': consts.META_WITH_MASK,
        'male': consts.META_MALE,
        'female': consts.META_FEMALE,
    }
    if attribute:
        if attribute.endswith('-age'):
            age = int(re.findall(r'(\d+)-age', attribute)[0])
            meta.update({consts.AGE_RANGE_STUB: (age, age+10)})
        else:
            meta.update(attribute_to_meta[attribute])
    return {
        'object_type': base,
        'meta': meta,
        'log_info': False,
    } | kwargs


class Object:
    FONT = 'courier.ttf'
    counter = 0

    def __init__(
            self,
            path: Optional[Path],
            camera: CameraData,
            client: ApiClient,
            base: BaseType,
            timestamp: TimestampType,
            draw_text: bool = False,
            roi: Optional[Roi] = None,
            meta: MetaType = {},
    ):
        self._id: IdIntType = None  # type: ignore[assignment]
        self._path = path
        self._base = base
        self._meta = meta | consts.META_ANY_QUALITY  # type: ignore[assignment]
        self._camera = camera
        self._client = client
        self._is_meta_required = True
        self._roi = roi
        self._timestamp = timestamp
        Object.counter += 1

        if draw_text:
            self._draw_text()

    @property
    def meta(self):
        return self._meta

    @classmethod
    def init_from_dict(cls, sender, data: ObjectData) -> Self:
        """ Init object by data from backend """
        obj = cls(
            path=None,
            camera=sender.get_camera_by_id(data.camera_id),
            client=sender.client,
            base=data.base,
            timestamp=data.timestamp,
            roi=data.roi,
        )
        obj.set_meta(data)
        return obj

    @cached_property
    def image(self) -> Image.Image:
        if not self._path:
            raise RuntimeError
        return Image.open(self._path)

    def __str__(self):
        return f'{self.base} at {self.timestamp} from {self.camera} id:{self.id}'

    @property
    def camera(self) -> CameraData:
        return self._camera

    @property
    def id(self) -> int:
        return self._id

    @property
    def datetime(self) -> datetime:
        return timestamp_to_date(self.timestamp)

    @property
    def timestamp(self) -> TimestampType:
        return self._timestamp

    @property
    def base(self) -> BaseType:
        return self._base

    @property
    def packet(self) -> Mapping[str, Any]:
        image_bytes = io.BytesIO()
        self.image.save(image_bytes, format='JPEG', exif=b'')
        image_packet = {
            'access_token': self._client.access_token,
            'label': BASE_TO_ID[self.base],
            'track_id': str(uuid.uuid4()),
            'camera_id': self._camera.id,
            'timestamp': int(self.timestamp * 1e6),
            'meta': self._meta,
            'score': 1.0,
            'im_bytes': image_bytes.getvalue(),
            'im_shape': (self.image.size[1], self.image.size[0], 3),
            'analytics': [f'{self.base}:dummy'],
            'roi': self._roi,
        }
        return image_packet

    def set_meta(self, obj: ObjectData) -> None:
        # TODO: set image_url
        # TODO: set parent id
        # TODO: set cluster size??
        self._meta.update(obj.meta)
        self._meta['is_reference'] = obj.is_reference  # lets consider `is_reference` as meta
        self._meta['matched'] = (obj.cluster_size or 0) > 1  # lets consider `matched` as meta
        self._id = obj.id
        self._is_meta_required = False

    def has_meta(self, req_meta: MetaType) -> bool:
        # NB: make sure you handle all stubs properly
        for req_key in req_meta:
            if req_key in (consts.AGE_RANGE_STUB, ):
                continue
            if req_key == consts.META_LIC_PLATE and req_meta[req_key] == '*':
                if self._meta.get(consts.META_LIC_PLATE):
                    return True  # object has any license plate
            if req_key not in self._meta:
                return False
            if self._meta[req_key] != req_meta[req_key]:
                return False
        return True

    def _draw_text(self) -> None:
        text = f"{self._camera['name']} ({Object.counter})\n{self.datetime}"
        font_size = 1
        font = ImageFont.truetype(self.FONT, font_size)
        img_width_segment = 1.1

        while font.getsize(text)[0] < img_width_segment * self.image.size[0]:
            font_size += 1
            font = ImageFont.truetype(self.FONT, font_size)

        drawer = ImageDraw.Draw(self.image)
        drawer.text(
            xy=(10, 100),
            text=text,
            fill=(0, 255, 0),
            font=font,
        )


class ImageSender:
    _default_attributes = {'face': 'female', 'vehicle': 'type-van', 'person': 'good-quality'}
    base_images_dir = Path('base_images')

    def __init__(self, client: ApiClient):
        self.client = client
        self._metareceiver_url = f'{get_env_data()["url"]}/meta-receiver/'
        self._objects = []
        self._requests_timeout = tuple(config.user_config['requests_timeout'])
        self._cameras_cached = None

    @property
    def cameras(self):
        """
        Return list of cameras from cache.
        Update cache if necessary.
        """
        if self._cameras_cached is None:
            log.info("Update camera cache")
            self._cameras_cached = get_cameras(self.client, "both")
        return self._cameras_cached

    def get_camera_by_id(self, id_: str):
        for camera in self.cameras:
            if camera.id == id_:
                return camera
        raise RuntimeError(f'No camera with id:{id_}')

    def clear_cache(self):
        log.info('Mark cameras cache as dirty (it will be updated next time)')
        self._cameras_cached = None

    def check_min_objects_count(
            self,
            conditions,
            cameras=None,
            meta=None, **kwargs) -> Self:
        # TODO: it is silly to apply 'meta' to different object types from 'conditions'
        cameras = self._normalize_cameras(cameras)
        kwargs['meta'] = meta  # kwargs for `objects_count`. but meta is required for `objects_count` and `send` methods
        for object_type, min_objects_amount in conditions.items():
            actual_count = self.objects_count(**parse_template(object_type, **kwargs), cameras=cameras)
            condition_str = f"min condition object_type:{object_type} {self._repr_meta(meta)}: {actual_count} >= {min_objects_amount}"
            objects_amount_required = min_objects_amount - actual_count
            if objects_amount_required <= 0:
                log.info(f"{condition_str} OK!")
                continue
            log.info(f"{condition_str}: need {objects_amount_required} more objects")
            self.send(
                camera=cameras[0],
                count=objects_amount_required,
                object_type=object_type,
                get_meta=False,
                meta=meta,
            )
        self.get_meta_information_from_backend()
        return self

    def check_max_objects_count(
            self,
            conditions: dict[str, int],
            cameras=None,
            **kwargs) -> Self:
        cameras = self._normalize_cameras(cameras)
        for object_type, max_objects_amount in conditions.items():
            actual_count = self.objects_count(**parse_template(object_type, **kwargs), cameras=cameras)
            condition_str = f"max condition object_type:{object_type}: {actual_count} <= {max_objects_amount}"
            if actual_count > max_objects_amount:
                raise PreconditionException(condition_str)
            else:
                log.info(f"{condition_str} OK!")
                continue
        return self

    def check_diff_objects_count_in_cameras(
            self,
            object_type: ImageTemplateType,
            *cam_sets,
            **kwargs) -> Self:
        """
        Make sure objects count in all camera sets is different.
        Make sure every camera set has at leat 1 object.
        """
        cam_sets = [self._normalize_cameras(cam_set) for cam_set in cam_sets]
        min_count = kwargs.pop('min_count', 1)

        for cam_set in cam_sets:
            if not cam_set:
                raise RuntimeError("camera set is empty")
            self.check_min_objects_count({object_type: min_count}, cameras=cam_set, **kwargs)

        sorted_count = sorted(
            [
                (cam_set, self.objects_count(**parse_template(object_type, **kwargs), cameras=cam_set))
                for cam_set in cam_sets
            ],
            key=lambda x: x[1],
        )

        for ix, (cam_set, _) in enumerate(sorted_count):
            if ix == 0:
                continue
            prev_objects_count = sorted_count[ix-1][1]
            self.check_min_objects_count(
                {object_type: prev_objects_count+ix},
                cameras=cam_set,
                **kwargs,
            )

        report = ""
        for cam_set in cam_sets:
            report += f" {self._repr_list_of_cameras(cam_set)}" \
                f"({self.objects_count(**parse_template(object_type, **kwargs), cameras=cam_set)})"
        log.info(f"Objects count of type {object_type}:{report}")
        return self

    def check_diff_objects_count(self, object_types, cameras=None, min_count=1, **kwargs):
        cameras = self._normalize_cameras(cameras)
        for object_type in object_types:
            self.check_min_objects_count({object_type: min_count}, cameras=cameras, **kwargs)

        sorted_count = sorted(
            [
                (object_type, self.objects_count(**parse_template(object_type, **kwargs), cameras=cameras))
                for object_type in object_types
            ],
            key=lambda x: x[1],
        )
        for ix, (object_type, _) in enumerate(sorted_count):
            if ix == 0:
                continue
            prev_objects_count = sorted_count[ix-1][1]
            self.check_min_objects_count(
                {object_type: prev_objects_count+ix},
                cameras=cameras,
                **kwargs,
            )

        report = ""
        for object_type in object_types:
            objects_count = self.objects_count(**parse_template(object_type, **kwargs), cameras=cameras)
            report += f" {object_type}({objects_count})"
        log.info(f"Objects count {self._repr_list_of_cameras(cameras)}:{report}")
        return self

    def objects(
            self,
            object_type,
            meta=None,
            cameras=None,
            timeslice=consts.DEFAULT_TIMESLICE,
            # detalization=None,
            log_info=True,
            date_from=None,
            date_to=None,
    ):
        """
        timeslice: None, 1h, 6h, 1d, 3d, 1w, 2w
        # TODO: support intervals
        """
        if date_from and timeslice:
            log.warning(f'Overwrite timeslice {timeslice} -> None (since date_from = {date_from})')
            timeslice = None

        meta = parse_template(object_type, meta=meta)['meta']
        base = parse_object_type(object_type)[0]
        if ('bad_quality' not in meta) and '_any_quality_stub' not in meta:
            meta.update(consts.META_GOOD_QUALITY)
        if consts.AGE_RANGE_STUB in meta and base != 'face':
            raise RuntimeError(f'Age range is available only for faces (base={base})')
        cameras = self._normalize_cameras(cameras)
        objects = tuple(filter(lambda x: x.camera.id in [c.id for c in cameras], self._objects))
        objects = tuple(filter(lambda x: x.base == base, objects))
        if consts.AGE_RANGE_STUB in meta:
            age_from, age_to = meta[consts.AGE_RANGE_STUB]
            objects = tuple(filter(lambda x: age_from <= (x._meta.get('age') or -1) <= age_to, objects))
        if timeslice:
            objects = filter_objects_by_timeslice(objects, lambda x: getattr(x, 'datetime'), timeslice)
        else:
            objects = filter_objects_by_timestamps(objects, lambda x: getattr(x, 'datetime'), date_from, date_to)

        objects = tuple(filter(lambda x: x.has_meta(meta), objects))
        if log_info:
            log.info(f"Image Sender: base:{base} timeslice:{timeslice} {self._repr_meta(meta)} {self._repr_list_of_cameras(cameras)}: {len(objects)} found")
        return objects

    def objects_count(self, *args, **kwargs):
        return len(self.objects(*args, **kwargs))

    def objects_count_for_ages(
            self,
            min_age: int,
            max_age: int,
            *args, **kwargs) -> int:
        suitable_objects = []
        for obj in self.objects('face', *args, **kwargs):
            if not obj._meta['age']:
                continue
            if min_age <= obj._meta['age'] <= max_age:
                suitable_objects.append(obj)
        log.info(f'Objects count for age range {min_age} .. {max_age}: {len(suitable_objects)}')
        return len(suitable_objects)

    def objects_count_in_interval(
            self,
            base: str,
            delta_from: Ago,
            delta_to: Ago,
            objects_to_send: int = 0,
            min_objects_count: int = 0,
    ) -> int:
        # TODO: explain what the hell is going on here...
        # TODO: add more logging
        # TODO: it is ok that this func is able to send and count objects?
        long_time_ago = Ago('-300d')
        delta_to = delta_to or Ago(0)
        delta_from = delta_from or long_time_ago
        assert delta_from < delta_to
        objects_count = self.objects_count(
            base, date_from=delta_from.dt, date_to=delta_to.dt, timeslice=None)
        log.info(f'Objects count of {base} between "{format_date_chart_like(delta_from.dt)}"'
                 f' ... "{format_date_chart_like(delta_to.dt)}": {objects_count}')

        diff = delta_to - delta_from
        send_time = (delta_from + diff * 0.2)
        log.info(f' - timestamp to send: "{format_date_chart_like(send_time.dt)}"')
        if objects_to_send:
            self.send(base, timestamp=send_time.timestamp, count=objects_to_send)
            objects_count += objects_to_send

        required_count = 0
        if min_objects_count:
            required_count = min_objects_count - objects_count
            if required_count > 0:
                self.send(base, timestamp=send_time.timestamp, count=required_count)
                objects_count += required_count

        return objects_count

    @staticmethod
    def _repr_meta(meta):
        meta_str = ""
        for meta_attribute in (meta or []):
            if meta_attribute == '_any_quality_stub':
                continue
            meta_str += f"{meta_attribute}:{meta[meta_attribute]} "
        return meta_str.strip() or "(no meta)"

    def _repr_list_of_cameras(self, cameras):
        if cameras is None:
            return f"(all {len(self.cameras)} cameras)"
        str_cameras = "("
        for camera in cameras:
            str_cameras += f"{camera.name}, "
        return str_cameras[:-2] + ")"

    def _normalize_cameras(self, cameras):
        """
        Converts user defined list of cameras into format which suitable for ImageSender
        """
        if cameras is None:
            return tuple(self.cameras)
        elif isinstance(cameras, str):
            return (get_camera_by_name(self.client, cameras), )
        elif isinstance(cameras, dict):
            return (cameras, )
        elif isinstance(cameras, (tuple, list)):
            if not cameras:
                return tuple()
            if isinstance(cameras[0], CameraData):
                return tuple(cameras)
            else:
                return tuple([get_camera_by_name(self.client, camera_name) for camera_name in cameras])
        else:
            raise RuntimeError(f"Unknown cameras type: {cameras}")

    @retry(ConnectionError, tries=3, delay=3)
    def _send_object(self, obj, remember=True):
        if not obj.camera.active:
            log.warning(f'{obj.camera} is not active')
        if obj.camera.archived:
            log.warning(f'{obj.camera} is archived')
        log.info(f'Send object: {obj} with meta {self._repr_meta(obj._meta)}')
        response = requests.post(
            self._metareceiver_url,
            headers={'Content-Type': 'application/msgpack'},
            data=msgpack.packb(obj.packet),
            timeout=self._requests_timeout,
        )
        try:
            data = response.json()
        except JSONDecodeError as exc:
            raise RuntimeError(f'Unable to parse metareceiver response: "{response.text}"') from exc
        if response.status_code == 422 and 'Unprocessable entity' in data['message']:
            raise UnprocessableEntityException(data['message'])
        if response.status_code != 200:
            raise RuntimeError(f'Bad response: {response.text}')

        if remember:
            self._objects.append(obj)
        else:
            log.warning(f'Do not remember object: {obj}')

        config.last_object_sent_time = now_pst()

    def init_objects(self, *args, **kwargs):
        def init_for_base(base, pgoffset, pgsize):
            items = self._request_last_objects(base, pgoffset=pgoffset, pgsize=pgsize, *args, **kwargs)
            log.info(f"\tGot {len(items)} {base} objects {pgoffset=} {pgsize=}")
            for item in items:
                self._objects.append(Object.init_from_dict(self, item))

        for base in ("face", "vehicle", "person"):
            log.info(f"Init {base} objects for {self.client}")
            init_for_base(base, 0, 250)

    def _request_last_objects(self, base, pgsize=100, pgoffset=0, *args, **kwargs):
        return search_api_v2(
            client=self.client,
            object_type=base,
            filters=consts.API_ANY_QUALITY | kwargs.pop('filters', {}),
            pgsize=pgsize,
            pgoffset=pgoffset,
            *args, **kwargs,
        )

    def get_template_path(self, object_type):
        base, attribute, _ = parse_object_type(object_type)

        if attribute is None and base in self._default_attributes:
            attribute = self._default_attributes[base]

        path = self.base_images_dir / base / f"{attribute}.jpg"
        return path

    def send(self, object_type, count=1, camera=None, roi=None, draw_text=False, timestamp=None,
             meta=None, get_meta=True, remember=True, wait_for_cluster=False):
        """
        Find picture by template `object_type`, craft Object and sent it `count` times to CERTAIN camera
        Sending to several cameras isn't supported right now

        TODO: make sure `object-handler` service has configuration "SKIP_OLD_MESSAGES: 0"
        Otherwise objects with timestamp older than 2h will be ignored.
        remember: Useful if you send objects to camera which isn't working
        """
        def _template_to_roi(template):
            return {
                'face-male': Roi({'x1': 0.1, 'y1': 0.05, 'x2': 0.9, 'y2': 0.75}),
            }.get(template, DEFAULT_ROI)

        if wait_for_cluster is True and get_meta is False:
            raise RuntimeError('You should "get_meta" to be able to "wait_for_cluster"')
        if config.pytest_options and config.pytest_options.skip_sender_tests:
            pytest.skip('Sending objects is not allowed')
        meta = meta or {}
        if camera is None:
            camera = self.cameras[0]
        if isinstance(camera, str):
            # example of camera id: d8a9a5a8-37b9-44cd-876a-7cfa800b5375
            if len(camera) == 36:
                camera = get_camera_by_id(self.client, camera)
            else:
                camera = get_camera_by_name(self.client, camera)

        timestamp = int(timestamp or time.time())
        log.info(f"Send template {object_type} {count} times to {camera}")
        base = parse_object_type(object_type)[0]
        assert base in BASE_TO_ID.keys()

        sent_objects = []

        with futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures_ = []
            for _ in range(count):
                image_obj = Object(
                    path=self.get_template_path(object_type),
                    camera=camera,
                    client=self.client,
                    base=base,
                    draw_text=draw_text,
                    timestamp=timestamp,
                    meta=meta,
                    roi=roi or _template_to_roi(object_type),
                )

                sent_objects.append(image_obj)
                futures_.append(
                    executor.submit(self._send_object, image_obj, remember=remember)
                )

            futures.wait(futures_)
            for future in futures_:
                if future.exception():
                    raise future.exception()

        if wait_for_cluster:
            objects_to_cluster = self._get_unknown_objects_from_backend(object_type)
        if get_meta:
            time.sleep(4)   # wait objects arrive. prevent retrying
            self.get_meta_information_from_backend()
        else:
            time.sleep(1)  # prevent timestamp collision
        if wait_for_cluster:
            self._wait_objects_are_in_cluster(objects_to_cluster)

        return sent_objects

    def _wait_objects_are_in_cluster(self, objects_to_cluster):
        ids = [o.id for o in objects_to_cluster]
        if not ids:
            return
        for _ in range(5):
            if self._do_objects_are_in_cluster(ids):
                return
            time.sleep(20)
        raise ClusterizationException

    def _do_objects_are_in_cluster(self, ids):
        cluster_sizes = [get_object(self.client, id).cluster_size for id in ids]
        log.info(f'Objects {ids} cluster size: {cluster_sizes}')
        return all(size > 1 for size in cluster_sizes)

    @retry(MetaInformationException, delay=10, tries=5)
    def _get_unknown_objects_from_backend(self, base):
        base = parse_object_type(base)[0]
        unknown_timestamps = set([o.timestamp for o in self._objects if o._is_meta_required is True])
        if not unknown_timestamps:
            return []
        unknown_objects = []
        for obj in search_api_v2(
                self.client,
                base,
                consts.API_ANY_QUALITY,
                order=consts.API_ORDER_DATE_DESC,
        ):
            if obj.timestamp in unknown_timestamps:
                unknown_objects.append(obj)
        if not unknown_objects:
            raise MetaInformationException('No unknown objects')
        log.info(f'Found {len(unknown_objects)} unknown objects')
        return unknown_objects

    def get_meta_information_from_backend(self):
        @retry(MetaInformationException, delay=10, tries=4)
        def _get_meta_for_base(base, objects_to_get_meta):
            log.info(f'Get meta for {len(objects_to_get_meta)} {base} objects')
            for obj_from_backend in self._request_last_objects(
                    base,
                    pgsize=250,
                    recursive=False,
                    filters=consts.API_ORDER_DATE_DESC,
            ):
                for obj in filter(lambda x: x._is_meta_required is True, objects_to_get_meta):
                    if obj.timestamp == obj_from_backend.timestamp:
                        obj.set_meta(obj_from_backend)
            objects_to_get_meta = tuple(filter(lambda x: x._is_meta_required is True, objects_to_get_meta))
            if objects_to_get_meta:
                raise MetaInformationException(
                    f"{base}: objects without meta: {len(objects_to_get_meta)}")

        for base in [consts.BASE_FACE, consts.BASE_VEHICLE, consts.BASE_PERSON]:
            objects_to_get_meta = tuple(filter(lambda x: x._is_meta_required is True and x.base == base, self._objects))
            if len(objects_to_get_meta) == 0:
                continue
            try:
                _get_meta_for_base(base, objects_to_get_meta)
            except MetaInformationException:
                for obj in filter(lambda x: x._is_meta_required is True, objects_to_get_meta):
                    log.error(f"{obj}: do not require meta any more")
                    obj._is_meta_required = False
                raise

    def send_from_dir(
            self,
            img_dir: str | Path,
            object_type: str,
            cameras: Any = None,
            # get_meta: bool = True,
    ) -> Sequence[ObjectData]:
        pgsize = 100
        img_dir = Path(img_dir)
        if config.pytest_options.skip_sender_tests:
            pytest.skip('Sending objects is not allowed')
        cameras = self._normalize_cameras(cameras)
        base = parse_object_type(object_type)[0]
        rois_file = img_dir / 'rois_for_images.json'
        if not rois_file.exists():
            log.warning(f"not found {rois_file}")
            rois = {}
        else:
            with open(rois_file, 'r') as f:
                rois = json.loads(f.read())

        objects_sent = 0
        timestamp_from = int(time.time())
        for img_path in img_dir.iterdir():
            if img_path.suffix != '.jpg':
                log.debug(f"not an image: {img_path}")
                continue
            image_obj = Object(
                path=img_path,
                camera=cameras[0],
                client=self.client,
                timestamp=TimestampType(int(time.time())),
                base=base,
                roi=rois.get(img_path.name, DEFAULT_ROI),
            )
            self._send_object(image_obj)
            objects_sent += 1

        assert objects_sent > 0  # self check
        assert pgsize > objects_sent  # self check

        last_objects = []  # fix reportPossiblyUnboundVariable
        for _ in range(5):
            last_objects = search_api_v2(
                self.client,
                object_type,
                recursive=True,
                order=consts.API_ORDER_DATE_DESC,
                pgsize=pgsize,
            )
            last_objects = filter_objects_by_timestamps(
                last_objects,
                lambda x: getattr(x, 'timestamp'),
                timestamp_from,
                time_to=int(time.time()),
            )
            if len(last_objects) == objects_sent:
                break
            else:
                log.warning(f'Wroung objects count: {len(last_objects)}, expected: {objects_sent}')
                time.sleep(10)
        else:
            raise RuntimeError(f'Wroung objects count: {len(last_objects)}, expected: {objects_sent}')

        for obj in last_objects:
            self._objects.append(
                Object.init_from_dict(self, obj)
            )
        return last_objects

    @allure.step("Wait autorefresh time (30+ sec)")
    def wait_autorefresh_time(self, requests_time_costs: int = 4):
        log.info(f"Wait autorefresh time: {consts.AUTOREFRESH_TIME} sec")
        time.sleep(consts.AUTOREFRESH_TIME + requests_time_costs)
        return self

    def check_objects_from_dir(self, img_dir, object_type, cameras=None):
        pgsize = 250
        img_dir = Path(img_dir)
        cameras = self._normalize_cameras(cameras)
        base = parse_object_type(object_type)[0]
        rois_file = img_dir / 'rois_for_images.json'
        if not rois_file.exists():
            log.warning(f"not found {rois_file}")
            rois = {}
        else:
            with open(rois_file, 'r') as f:
                rois = json.loads(f.read())

        timestamp_to_path = {}
        timestamp_from = int(time.time())
        for img_path in img_dir.iterdir():
            if img_path.suffix != '.jpg':
                log.warning(
                    'Not an image: '
                    f'{shutil.move(img_path, img_path.parent / "not_an_image")}')
                continue
            image_obj = Object(
                path=img_path,
                camera=cameras[0],
                client=self.client,
                timestamp=int(time.time()),
                base=base,
                roi=rois.get(img_path.name, DEFAULT_ROI),
            )
            try:
                self._send_object(image_obj)
            except UnprocessableEntityException:
                log.warning(
                    'Invalid image: '
                    f'{shutil.move(img_path, img_path.parent / "unprocessable")}')
            else:
                timestamp_to_path[image_obj.timestamp] = img_path
            finally:
                time.sleep(1.1)

        last_objects = search_api_v2(
            self.client,
            object_type,
            recursive=True,
            order=consts.API_ORDER_DATE_DESC,
            pgsize=pgsize,
        )
        last_objects = filter_objects_by_timestamps(
            last_objects,
            lambda x: getattr(x, 'timestamp'),
            timestamp_from,
            time_to=int(time.time()),
        )

        bad_quality_dir = img_dir / "bad_quality/"
        if not bad_quality_dir.exists():
            bad_quality_dir.mkdir()

        for timestamp, img_path in timestamp_to_path.items():
            if timestamp not in [o.timestamp for o in last_objects]:
                new_path = shutil.move(img_path, bad_quality_dir)
                log.warning(f'Bad quality: {new_path}')
