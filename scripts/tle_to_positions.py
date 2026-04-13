from sgp4.api import Satrec, jday
from datetime import datetime, timedelta
import pandas as pd
import math
import argparse


# converter ECI -> lat/lon/alt
def eci_to_llh(x,y,z):
    lon = math.degrees(math.atan2(y, x))
    lat = math.degrees(math.atan2(z, (x*x+y*y)**0.5))
    alt = (x*x+y*y+z*z)**0.5 - 6378
    return lat, lon, alt

def do_it(file_name):
    rows = []

    with open(file_name) as f:
        lines = [l.strip() for l in f if l.strip()]

    for i in range(0, len(lines), 3):

        if i%(3 * 100) == 0:
            print(i/3)

        name = lines[i]
        l1 = lines[i+1]
        l2 = lines[i+2]

        sat = Satrec.twoline2rv(l1, l2)

        start = datetime.utcnow()

        # gerar 2h de órbita (1 ponto/30s)
            # 30 min -> 5 em 5 min
        for s in range(0, 1800, 300):

            t = start + timedelta(seconds=s)
            jd, fr = jday(t.year,t.month,t.day,t.hour,t.minute,t.second)

            e, r, v = sat.sgp4(jd, fr)

            if e == 0:
                lat, lon, alt = eci_to_llh(*r)
                rows.append([name, t, lat, lon, alt])

        df = pd.DataFrame(rows, columns=["sat","time","lat","lon","alt_km"])
        df.to_csv("positions.csv", index=False)

    print("positions.csv criado ✔")

if __name__ == "__main__":
    do_it("tle.txt")