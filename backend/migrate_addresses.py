"""Explicit one-time migration; environment variables select the Redis destination."""
import argparse
import getpass
import os
import json
from .addresses import FILE, AddressInput
from .cloud_store import RedisStore

def main():
    parser=argparse.ArgumentParser(description='Copy saved local addresses to Redis without removing existing cloud entries.')
    parser.add_argument('--prefix',required=True,help='The destination NEST_REDIS_PREFIX, e.g. nestnnook:production')
    args=parser.parse_args()
    os.environ['NEST_REDIS_PREFIX']=args.prefix
    if not os.getenv('UPSTASH_REDIS_REST_URL'):os.environ['UPSTASH_REDIS_REST_URL']=input('Upstash REST URL: ').strip()
    if not os.getenv('UPSTASH_REDIS_REST_TOKEN'):os.environ['UPSTASH_REDIS_REST_TOKEN']=getpass.getpass('Upstash REST token (hidden): ').strip()
    store=RedisStore()
    addresses=json.loads(FILE.read_text(encoding='utf-8'))
    if not isinstance(addresses,list):raise SystemExit('Expected a list of addresses.')
    validated=[AddressInput(address=value).address for value in addresses]
    for value in validated:
        if not store.add_address(value):raise SystemExit('The destination address list is full.')
    print(f'Imported {len(validated)} addresses. Existing entries were retained; duplicates were skipped.')

if __name__=='__main__':main()
