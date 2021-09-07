import requests
import sys


# convert meters to feet
def m_toft(m):
    return float(m) * 3.2808


# retrieve USGS altitude
def usgs_alt(lat, lon):
    url = "http://nationalmap.gov/epqs/pqs.php"
    params = {"x": lon, "y": lat, "units": "Meters", "output": "json"}
    try:
        r = requests.get(url, params=params)
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)
    if r.status_code == 200:
        try:
            data = r.json()
        except e:
            print(e)
            sys.exit(1)

        alt = float(data["USGS_Elevation_Point_Query_Service"]["Elevation_Query"]["Elevation"])
        # print(f"USGS alt: {alt:.1f} m, {m_toft(alt):.1f} ft")
        return alt


def main():
    usgs_alt(42.955701, -76.921108)


if __name__ == "__main__":
    # make sure we can run this
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        main()
    else:
        print("python 3.8 or better required")
