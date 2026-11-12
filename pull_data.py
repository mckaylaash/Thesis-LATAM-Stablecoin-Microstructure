from io import BytesIO
from bs4 import BeautifulSoup  # or from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
import requests

# temp sandbox data
base_url = 'https://vpn.princeton.edu/https/sandbox-dss1.lib.princeton.edu/Kaiko/'

# authentication requirement from VPN
session = requests.Session()

# Sandbox folder layout
# Kaiko/trades/btso/spot/ --> usdtbrl, usdtars, usdtmxn
# Kaiko/trades/merc/spot/ --> usdtbrl, usdcbrl
# Kaiko/trades/bnce/spot/ --> usdtbrl, 

TARGETS = [
    # Bitso (btso) 
    {'exchange': 'btso', 'pair': 'usdtars'},
    {'exchange': 'btso', 'pair': 'usdtbrl'},
    {'exchange': 'btso', 'pair': 'usdtmxn'},
    # Mercado Bitcoin (merc) 
    {'exchange': 'merc', 'pair': 'usdtbrl'},
    {'exchange': 'merc', 'pair': 'usdcbrl'},
    # Binance (bnce) 
    {'exchange': 'bnce', 'pair': 'usdtbrl'},
]

def crawl_directory_for_files(url, session):
  """Recursively crawls Apache directory indexes using urljoin.

  Removed the leading slash skip so proxy-absolute links are processed.
  """
  file_urls = []
  try:
    response = session.get(url)
    if response.status_code != 200:
      print(f"  ⚠️ Failed to access {url} (HTTP {response.status_code})")
      return file_urls

    soup = BeautifulSoup(response.text, "html.parser")
    for link in soup.find_all("a"):
      href = link.get("href", "")

      # Skip parent directories and query parameters only
      if not href or href == "../" or href.startswith("?"):
        continue

      # Safely resolve full URL (urljoin handles leading slashes perfectly)
      sub_url = urljoin(url, href)

      # Diagnostic print to see what is being crawled
      # print(f"    Found link: {href}")

      if href.endswith("/"):
        # Recursively crawl subfolders (e.g. monthly/daily partitions)
        file_urls.extend(crawl_directory_for_files(sub_url, session))
      elif href.endswith((".csv", ".gz")):
        # Data file found
        file_urls.append(sub_url)

  except Exception as e:
    print(f"  ❌ Error crawling {url}: {e}")

  return file_urls


def load_all_kaiko_data(targets):
  panel_data = {}

  for target in targets:
    exch = target["exchange"]
    pair = target["pair"]

    folder_url = f"{base_url}trades/{exch}/spot/{pair}/"
    print(
        f"Processing -> Exchange: {exch.upper()} | Pair: {pair}\n  Crawling"
        f" subfolders..."
    )

    try:
      # Recursively collect all data file URLs across all monthly folders
      file_urls = crawl_directory_for_files(folder_url, session)

      if not file_urls:
        print("  ⚠️ No data files found across subdirectories.")
        continue

      print(f"  📥 Found {len(file_urls):,} data files. Downloading...")

      chunk_dfs = []
      for file_url in file_urls:
        file_res = session.get(file_url)

        if file_res.status_code == 200:
          is_compressed = file_url.endswith(".gz")
          compression_type = "gzip" if is_compressed else None

          df = pd.read_csv(
              BytesIO(file_res.content),
              compression=compression_type,
              dtype={
                  "id": "string",
                  "exchange": "string",
                  "symbol": "string",
                  "price": "float64",
                  "amount": "float64",
                  "sell": "boolean",
              },
          )
          chunk_dfs.append(df)

      if chunk_dfs:
        master_df = pd.concat(chunk_dfs, ignore_index=True)
        master_df["timestamp"] = pd.to_datetime(
            master_df["date"], unit="ms", utc=True
        )
        master_df.set_index("timestamp", inplace=True)
        master_df.sort_index(inplace=True)

        panel_data[f"{exch}_{pair}"] = master_df
        print(
            f"  ✅ Successfully loaded {len(master_df):,} total rows for"
            f" {exch}_{pair}.\n"
        )

    except Exception as e:
      print(f"  ❌ Error processing {exch}/{pair}: {e}\n")

  return panel_data


if __name__ == "__main__":
  loaded_panel_data = load_all_kaiko_data(TARGETS)