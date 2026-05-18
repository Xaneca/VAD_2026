information needs to be checked

# 🛰️ Orbital Objects Dataset Documentation

## 1. Basic Identifiers and Metadata
* **`JCAT`**: Jonathan's Space Report catalog number (assigned by astrophysicist Jonathan McDowell).
* **`NORAD_CAT_ID`**: NORAD Catalog ID (also known as Satellite Number or Space-Track ID). This is the primary 5-digit numerical identifier.
* **`OBJECT_ID`**: International Designator (COSPAR ID), e.g., `1998-067A` (Launch Year - Launch Number of the year - Piece identifier).
* **`NAME`**: Official name of the satellite or orbital object.
* **`OWNER`**: Code representing the satellite operator or owner (e.g., SpaceX, NASA, ESA).
* **`COUNTRY`**: Country of origin or country responsible for the object's registration.
* **`MANUFACTURER`**: Company that built the object.

---

## 2. Physical Characteristics
* **`MASS`**: Total estimated or recorded mass of the object (typically expressed in kg).
* **`LENGTH`**: Length of the object's main body (in meters).
* **`DIAMETER`**: Diameter of the object (in meters).
* **`SPAN`**: Maximum span of the object (in meters), usually measured with solar arrays fully deployed.
* **`SHAPE`**: Geometric shape of the object (e.g., cylinder, box, sphere).

---

## 3. Timeline and History (Dates)
* **`LAUNCH_DATE`**: The date and time when the object was launched into space.
* **`PARENT`**: Identifier of the "parent" object from which this piece separated (relevant for debris or components released from a rocket or station).
* **`SEPARATION_DATE`**: The date when the object physically detached from its parent object.
* **`DECAY_DATE`**: The date when the object re-entered Earth's atmosphere and burned up/fell (empty for objects still in orbit).

---

## 4. Operational and Orbital States
* **`OBJECT_TYPE`**: Classification of the space object type.
  * *Available options:* `Space station`, `Component`, `Rocket body`, `Satellite`, `Debris`, `In analysis`, `Unknown`.
* **`ORB_STATUS`**: Macro orbital status (e.g., in orbit, decayed).
* **`OPS_STATUS_CODE`**: Current operational status code of the satellite.
  * *Options and custom mapping:*
    * `+` : Operational ➔ **O** (Operational)
    * `-` : Nonoperational ➔ **R** (Nonoperational)
    * `P` : Partially Operational ➔ **O** (Operational)
    * `B` : Backup/Standby ➔ **AR** (Active Reserve)
    * `S` : Spare ➔ **AR** (Active Reserve)
    * `X` : Extended Mission ➔ **O** (Operational)
    * `D` : Decayed ➔ **D** (Decayed)
* **`LAUNCH_SITE`**: Code or name of the launch base from which the rocket departed (e.g., KSC, VAFB, CCFS, Baikonur).
* **`ORBIT_TYPE`**: Classification of the orbit based on altitude ranges:
  * *Available options:*
    * **LEO** (Low Earth Orbit): 500 km – 2,000 km
    * **MEO** (Medium Earth Orbit): 2,000 km – 35,786 km
    * **GEO** (Geostationary Orbit): 35,786 km

---

## 5. Orbital Elements (SGP4 / TLE Data)
* **`EPOCH`**: Exact date and time of the capture (snapshot) of these orbital elements.
* **`PERIOD`**: Orbital period. The time it takes for the object to complete one full revolution around Earth (in minutes).
* **`INCLINATION`**: The angle of the orbit relative to Earth's equator (in degrees, from 0° to 180°).
* **`PERIGEE`**: The altitude of the closest point of the orbit to Earth's surface (in km).
* **`APOGEE`**: The altitude of the farthest point of the orbit from Earth's surface (in km).
* **`ECCENTRICITY`**: Orbit eccentricity (indicates how elliptical or circular the orbit is; 0 represents a perfect circle).
* **`MEAN_MOTION`**: The number of revolutions the object makes around Earth per day.
* **`RA_OF_ASC_NODE`**: Right Ascension of the Ascending Node (RAAN). Angle orienting the orbital plane in space (in degrees).
* **`ARG_OF_PERICENTER`**: Argument of Pericenter (or Perigee). Angle orienting the orbit's ellipse within its own plane (in degrees).
* **`MEAN_ANOMALY`**: Position of the satellite along its orbital ellipse calculated from the perigee (in degrees).
* **`TLE_LINE1`**: Raw text string representing the first line of the TLE (Two-Line Element set) format.
* **`TLE_LINE2`**: Raw text string representing the second line of the TLE format.

---

## 6. Special Categories and Constellations (Flags / Groups)
*These columns correspond to the CelesTrak grouping classifications. They usually act as binary flags (0/1 or True/False) indicating whether an object belongs to that specific category.*

### Subgroup: Communications and Internet Megaconstellations
* **`COMMUNICATION`**: General category flag for telecommunication satellites.
* **`EUTELSAT`, `GLOBALSTAR`, `INTELSAT`, `IRIDIUM_NEXT`, `ONEWEB`, `ORBCOMM`, `SES`, `STARLINK`, `TELESAT`**: Flags for their respective commercial telecommunication constellations.
* **`HULIANWANG_DIGUI`**: Flag for the Chinese state-owned low Earth orbit (LEO) internet constellation.
* **`QIANFAN`**: Flag for the Chinese "Thousand Sails" (G60) satellite internet constellation.
* **`KUIPER`**: Flag for Amazon's upcoming satellite internet network (Project Kuiper).
* **`OTHER_COMM`**: Other communication satellites not belonging to the major fleets listed above.
* **`AMATEUR_RADIO`**: Satélites used for amateur radio tracking and communication.
* **`SATNOGS`**: Satellites integrated into or monitored by the SatNOGS open global network.

### Subgroup: Navigation and Global Positioning
* **`NAVIGATION`**: General category flag for navigation satellites.
* **`GNSS`**: Global Navigation Satellite Systems (generic term).
* **`GPS_OPERATIONAL`**: Active satellites in the United States GPS network.
* **`GLONASS_OPERATIONAL`**: Active satellites in the Russian GLONASS network.
* **`GALILEO`**: Active satellites in the European Union Galileo network.
* **`BEIDOU`**: Active satellites in the Chinese BeiDou network.
* **`AUGMENTATION_SYSTEM`**: Satellite-Based Augmentation Systems (SBAS, EGNOS, WAAS) used to improve navigation accuracy.
* **`NNSS`, `RUSSIAN_LEO_NAVIGATION`**: Legacy or specific low Earth orbit navigation networks.

### Subgroup: Weather and Earth Observation
* **`WEATHER`**: General category flag for meteorological satellites.
* **`GOES`**: Geostationary Operational Environmental Satellites operated by NOAA (USA).
* **`NOAA`**: Polar-orbiting weather satellites operated by the NOAA agency.
* **`EARTH_RESOURCES`**: Satellites focused on monitoring land and natural resources (e.g., the Landsat series).
* **`DISASTER_MONITORING`**: Satellites dedicated to natural disaster management and emergency monitoring.
* **`PLANET`, `SPIRE`**: Flags for the micro-satellite constellations owned by Planet Labs and Spire Global.
* **`ARGOS`**: Environmental data collection and wildlife/buoy location system.

### Subgroup: Scientific, Defense, and Others
* **`SCIENTIFIC`**: Satellites intended for scientific research and astrophysics.
* **`EDUCATION`**: University or purely educational/pedagogical satellites.
* **`ENGINEERING`**: Technology demonstration satellites used to validate new hardware components in space.
* **`GEODETIC`**: Satellites used to map Earth's exact geometric shape and gravitational field.
* **`SPACE_EARTH`**: Deep space observation satellites operating from Earth's orbit.
* **`ACTIVE_GEO`**: Identifies whether the object is currently active and positioned in the Geostationary orbit belt.
* **`CUBESTATS`**: Category dedicated to standard CubeSats formats.
* **`MILITARY`**: Satellites used for defense, reconnaissance, or national security purposes.
* **`RADAR_CALIBRATION`**: Objects (often old metallic spheres or stable debris) used to calibrate ground-based radar systems.
* **`BRIGHTEST`**: List of space objects with high visual magnitude (easiest to spot with the naked eye from Earth).
* **`SARSAT`**: Satellites equipped with Search and Rescue payloads.
* **`TDRSS`**: NASA's Tracking and Data Relay Satellite System network.
* **`MISCELLANEOUS`, `OTHER`**: Residual categories for objects that do not fit into any of the predefined groups.

---

## ❓ Missing Information & Questions to Clarify
*Please update the documentation above once you verify these specific dataset traits:*

1. **`PRIMARY`**: What does this column store? Is it a numerical ID pointing to the master satellite payload of a debris piece, or is it a binary flag (0/1) indicating a primary payload versus a secondary payload?
2. **`GEO_PROTECTED_ZONE` & `GEO_PROTECTED_ZONE_PLUS`**: Do these hold boolean flags (True/False) checking if a satellite complies with geostationary protection zones, or do they contain specific coordinate strings?
3. **`MOVERS`**: What is the data type and purpose of this column in your specific pipeline? (Usually, CelesTrak uses this for objects that recently maneuvered or were launched in the last 30 days).
4. **Category Flags (Section 6)**: Are these coded as integers (`0`/`1`), booleans (`True`/`False`), or strings in your current CSV file?
