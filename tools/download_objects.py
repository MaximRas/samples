'''
available filters:
 - image_quality:good
 - matched:all
 - is_reference:all
FACE:
 - person_glasses:all
 - person_beard:all
 - person_mask:all
 - person_age:35-99

Example:
python -B tools/download_objects.py --env prod --company "Metapix"
  --email mrasulzoda@metapix.ai --base face -n 100
  --filters mask-good --output C:/Job/test --pgoffset 200
'''
from pathlib import Path
import argparse
import logging
import random

import requests

import consts
from tools import config
from tools.client import ApiClient
from tools.search import search_api_v2
from tools.users import filter_companies
from tools.users import get_available_companies
from tools.users import init_client
from tools.users import set_active_company

log = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=str, required=True)
    parser.add_argument("--base", type=str, required=True)
    parser.add_argument("--filters", type=str, required=False)
    parser.add_argument("-n", type=int, required=True)
    parser.add_argument("--random", default=False, action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument('--company', type=str, default=None, required=True)
    parser.add_argument('--email', type=str, required=True)
    parser.add_argument('--password', type=str, default="String!2")
    parser.add_argument('--pgoffset', type=int, default=0)
    parser.add_argument('--pgsize', type=int, default=100)

    args = parser.parse_args()
    config.environment = args.env
    config.load_config("config.yaml")

    client = ApiClient()

    if args.email:
        client = init_client(ApiClient(), args.email, args.password)

    if args.company:
        company = filter_companies(get_available_companies(client), args.company)
        set_active_company(client, company)

    items = search_api_v2(client, args.base, args.filters,
                          pgsize=args.pgsize,
                          pgoffset=args.pgoffset,
                          order=consts.API_ORDER_CLUSTER_SIZE)
    print(f"{len(items)} items have been found")
    if not items:
        print("no data")
    if len(items) <= args.n or not args.random:
        items = items[:args.n]
    else:
        print("perform sampling of random items")
        items = random.sample(items, k=args.n)
    for item in items:
        output_file = args.output / f'{item.id}.jpg'
        response = requests.get(item.image_url)
        response.raise_for_status()
        with open(output_file, "wb") as fp:
            fp.write(response.content)
            print(f"object {item.id} -> {output_file}")
