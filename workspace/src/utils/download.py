import urllib.request

file_url = "https://example.com/path/to/your/image.jpg"  # Replace with the actual URL
local_filename = "downloaded_image.jpg"  # Name to save the file as locally

try:
    urllib.request.urlretrieve(file_url, local_filename)
    print(f"File '{local_filename}' downloaded successfully.")
except urllib.error.URLError as e:
    print(f"Error downloading file: {e}")

class Download:
  def __init__(self,)
