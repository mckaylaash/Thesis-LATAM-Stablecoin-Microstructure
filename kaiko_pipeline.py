from io import BytesIO
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
import requests

# Base configuration for Princeton DSS sandbox
BASE_URL = 'https://vpn.princeton.edu/https/sandbox-dss1.lib.princeton.edu/Kaiko/'
SESSION = requests.Session()

# Active browser session tokens (verified working)
SESSION.cookies.set(
    'GP_SESSION_CK',
    'cguAIlucsUbPqiZ6Ij8Gii6TmGcJVHZ7',
    domain='vpn.princeton.edu',
)
SESSION.cookies.set(
    'SESSID', '649e6feb-ad94-4232-8eda-ea5c3b2c36b7', domain='vpn.princeton.edu'
)

# Sandbox folder layout
# Kaiko/trades/btso/spot/ --> usdtbrl, usdtars, usdtmxn
# Kaiko/trades/merc/spot/ --> usdtbrl, usdcbrl
# Kaiko/trades/bnce/spot/ --> usdtbrl, 

TARGETS = [
    # Bitso (btso) spot pairs
    {'exchange': 'btso', 'pair': 'usdtars'},
    {'exchange': 'btso', 'pair': 'usdtbrl'},
    {'exchange': 'btso', 'pair': 'usdtmxn'},
    # Mercado Bitcoin (merc) spot pairs
    {'exchange': 'merc', 'pair': 'usdtbrl'},
    {'exchange': 'merc', 'pair': 'usdcbrl'},
    # Binance (bnce) spot pairs
    {'exchange': 'bnce', 'pair': 'usdtbrl'},
]


def get_monthly_partition_urls(pair_folder_url):
  """Scrapes the pair root folder to extract valid monthly subdirectories

  (e.g., '2024-04/'), preventing infinite recursive crawling traps.
  """
  partition_urls = []
  try:
    res = SESSION.get(pair_folder_url)
    if res.status_code != 200:
      return partition_urls

    soup = BeautifulSoup(res.text, 'html.parser')
    for link in soup.find_all('a'):
      href = link.get('href', '')
      # Match standard YYYY-MM subfolders
      if href and href.endswith('/') and '-' in href and len(href.strip('/')) >= 7:
        full_sub_url = urljoin(pair_folder_url, href)
        partition_urls.append(full_sub_url)
  except Exception as e:
    print(f'  ❌ Error fetching partitions for {pair_folder_url}: {e}')

  return partition_urls


def get_files_in_partition(partition_url):
  """Extracts all .csv or .gz data files sitting inside a monthly partition folder."""
  file_urls = []
  try:
    res = SESSION.get(partition_url)
    if res.status_code != 200:
      return file_urls

    soup = BeautifulSoup(res.text, 'html.parser')
    for link in soup.find_all('a'):
      href = link.get('href', '')
      if href and href.endswith(('.csv', '.gz')):
        full_file_url = urljoin(partition_url, href)
        file_urls.append(full_file_url)
  except Exception as e:
    print(f'  ❌ Error reading partition {partition_url}: {e}')

  return file_urls


def load_kaiko_panel(targets):
  panel_data = {}

  for target in targets:
    exch = target['exchange']
    pair = target['pair']
    pair_folder_url = f'{BASE_URL}trades/{exch}/spot/{pair}/'

    print(f'Processing -> Exchange: {exch.upper()} | Pair: {pair}')

    # Step 1: Get monthly folders
    partition_urls = get_monthly_partition_urls(pair_folder_url)
    if not partition_urls:
      print('  ⚠️ No monthly partitions found.')
      continue

    print(f'  📁 Found {len(partition_urls)} monthly folders. Gathering files...')

    # Step 2: Collect all file URLs across partitions
    all_file_urls = []
    for p_url in partition_urls:
      all_file_urls.extend(get_files_in_partition(p_url))

    if not all_file_urls:
      print('  ⚠️ No trade files found inside monthly partitions.')
      continue

    print(f'  📥 Downloading {len(all_file_urls)} data chunks...')

    # Step 3: Stream and parse chunks into memory
    chunk_dfs = []
    for file_url in all_file_urls:
      file_res = SESSION.get(file_url)
      if file_res.status_code == 200:
        is_compressed = file_url.endswith('.gz')
        compression_type = 'gzip' if is_compressed else None

        df = pd.read_csv(
            BytesIO(file_res.content),
            compression=compression_type,
            dtype={
                'id': 'string',
                'exchange': 'string',
                'symbol': 'string',
                'price': 'float64',
                'amount': 'float64',
                'sell': 'boolean',
            },
        )
        chunk_dfs.append(df)

    # Step 4: Concatenate and index by UTC timestamp
    if chunk_dfs:
          master_df = pd.concat(chunk_dfs, ignore_index=True)
          master_df['timestamp'] = pd.to_datetime(
              master_df['date'], unit='ms', utc=True
          )
          master_df.set_index('timestamp', inplace=True)
          master_df.sort_index(inplace=True)

          # 💡 Save directly to disk as a compressed Parquet file
          file_name = f'{exch}_{pair}_trades.parquet'
          master_df.to_parquet(file_name, compression='snappy')
          print(
              f'  💾 Saved {len(master_df):,} rows to disk: {file_name}\n'
          )

          # Free up RAM immediately after saving
          del master_df
          chunk_dfs.clear()

  return panel_data


if __name__ == '__main__':
  dataset_panel = load_kaiko_panel(TARGETS)