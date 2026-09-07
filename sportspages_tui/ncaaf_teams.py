"""Static NCAAF (FBS, Division I top tier) team data, via ESPN's group 80,
tagged with conference. Ids and abbreviations mirror the same table used
in the Flutter sibling app's ncaaf_teams.dart.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NcaafTeamInfo:
    city: str
    name: str
    abbreviation: str
    conference: str
    espn_id: int

    @property
    def full_name(self) -> str:
        return f"{self.city} {self.name}"


CONFERENCES = [
    "ACC",
    "American",
    "Big 12",
    "Big Ten",
    "Conference USA",
    "Independent",
    "MAC",
    "Mountain West",
    "Pac-12",
    "SEC",
    "Sun Belt",
]

TEAMS: list[NcaafTeamInfo] = [
    NcaafTeamInfo("Boston College", "Eagles", "BC", "ACC", 103),
    NcaafTeamInfo("California", "Golden Bears", "CAL", "ACC", 25),
    NcaafTeamInfo("Clemson", "Tigers", "CLEM", "ACC", 228),
    NcaafTeamInfo("Duke", "Blue Devils", "DUKE", "ACC", 150),
    NcaafTeamInfo("Florida State", "Seminoles", "FSU", "ACC", 52),
    NcaafTeamInfo("Georgia Tech", "Yellow Jackets", "GT", "ACC", 59),
    NcaafTeamInfo("Louisville", "Cardinals", "LOU", "ACC", 97),
    NcaafTeamInfo("Miami", "Hurricanes", "MIA", "ACC", 2390),
    NcaafTeamInfo("NC State", "Wolfpack", "NCSU", "ACC", 152),
    NcaafTeamInfo("North Carolina", "Tar Heels", "UNC", "ACC", 153),
    NcaafTeamInfo("Pittsburgh", "Panthers", "PITT", "ACC", 221),
    NcaafTeamInfo("SMU", "Mustangs", "SMU", "ACC", 2567),
    NcaafTeamInfo("Stanford", "Cardinal", "STAN", "ACC", 24),
    NcaafTeamInfo("Syracuse", "Orange", "SYR", "ACC", 183),
    NcaafTeamInfo("Virginia", "Cavaliers", "UVA", "ACC", 258),
    NcaafTeamInfo("Virginia Tech", "Hokies", "VT", "ACC", 259),
    NcaafTeamInfo("Wake Forest", "Demon Deacons", "WAKE", "ACC", 154),
    NcaafTeamInfo("Army", "Black Knights", "ARMY", "American", 349),
    NcaafTeamInfo("Charlotte", "49ers", "CLT", "American", 2429),
    NcaafTeamInfo("East Carolina", "Pirates", "ECU", "American", 151),
    NcaafTeamInfo("Florida Atlantic", "Owls", "FAU", "American", 2226),
    NcaafTeamInfo("Memphis", "Tigers", "MEM", "American", 235),
    NcaafTeamInfo("Navy", "Midshipmen", "NAVY", "American", 2426),
    NcaafTeamInfo("North Texas", "Mean Green", "UNT", "American", 249),
    NcaafTeamInfo("Rice", "Owls", "RICE", "American", 242),
    NcaafTeamInfo("South Florida", "Bulls", "USF", "American", 58),
    NcaafTeamInfo("Temple", "Owls", "TEM", "American", 218),
    NcaafTeamInfo("Tulane", "Green Wave", "TULN", "American", 2655),
    NcaafTeamInfo("Tulsa", "Golden Hurricane", "TLSA", "American", 202),
    NcaafTeamInfo("UAB", "Blazers", "UAB", "American", 5),
    NcaafTeamInfo("UTSA", "Roadrunners", "UTSA", "American", 2636),
    NcaafTeamInfo("Arizona", "Wildcats", "ARIZ", "Big 12", 12),
    NcaafTeamInfo("Arizona State", "Sun Devils", "ASU", "Big 12", 9),
    NcaafTeamInfo("BYU", "Cougars", "BYU", "Big 12", 252),
    NcaafTeamInfo("Baylor", "Bears", "BAY", "Big 12", 239),
    NcaafTeamInfo("Cincinnati", "Bearcats", "CIN", "Big 12", 2132),
    NcaafTeamInfo("Colorado", "Buffaloes", "COLO", "Big 12", 38),
    NcaafTeamInfo("Houston", "Cougars", "HOU", "Big 12", 248),
    NcaafTeamInfo("Iowa State", "Cyclones", "ISU", "Big 12", 66),
    NcaafTeamInfo("Kansas", "Jayhawks", "KU", "Big 12", 2305),
    NcaafTeamInfo("Kansas State", "Wildcats", "KSU", "Big 12", 2306),
    NcaafTeamInfo("Oklahoma State", "Cowboys", "OKST", "Big 12", 197),
    NcaafTeamInfo("TCU", "Horned Frogs", "TCU", "Big 12", 2628),
    NcaafTeamInfo("Texas Tech", "Red Raiders", "TTU", "Big 12", 2641),
    NcaafTeamInfo("UCF", "Knights", "UCF", "Big 12", 2116),
    NcaafTeamInfo("Utah", "Utes", "UTAH", "Big 12", 254),
    NcaafTeamInfo("West Virginia", "Mountaineers", "WVU", "Big 12", 277),
    NcaafTeamInfo("Illinois", "Fighting Illini", "ILL", "Big Ten", 356),
    NcaafTeamInfo("Indiana", "Hoosiers", "IU", "Big Ten", 84),
    NcaafTeamInfo("Iowa", "Hawkeyes", "IOWA", "Big Ten", 2294),
    NcaafTeamInfo("Maryland", "Terrapins", "MD", "Big Ten", 120),
    NcaafTeamInfo("Michigan", "Wolverines", "MICH", "Big Ten", 130),
    NcaafTeamInfo("Michigan State", "Spartans", "MSU", "Big Ten", 127),
    NcaafTeamInfo("Minnesota", "Golden Gophers", "MINN", "Big Ten", 135),
    NcaafTeamInfo("Nebraska", "Cornhuskers", "NEB", "Big Ten", 158),
    NcaafTeamInfo("Northwestern", "Wildcats", "NU", "Big Ten", 77),
    NcaafTeamInfo("Ohio State", "Buckeyes", "OSU", "Big Ten", 194),
    NcaafTeamInfo("Oregon", "Ducks", "ORE", "Big Ten", 2483),
    NcaafTeamInfo("Penn State", "Nittany Lions", "PSU", "Big Ten", 213),
    NcaafTeamInfo("Purdue", "Boilermakers", "PUR", "Big Ten", 2509),
    NcaafTeamInfo("Rutgers", "Scarlet Knights", "RUTG", "Big Ten", 164),
    NcaafTeamInfo("UCLA", "Bruins", "UCLA", "Big Ten", 26),
    NcaafTeamInfo("USC", "Trojans", "USC", "Big Ten", 30),
    NcaafTeamInfo("Washington", "Huskies", "WASH", "Big Ten", 264),
    NcaafTeamInfo("Wisconsin", "Badgers", "WIS", "Big Ten", 275),
    NcaafTeamInfo("Delaware", "Blue Hens", "DEL", "Conference USA", 48),
    NcaafTeamInfo("Florida International", "Panthers", "FIU", "Conference USA", 2229),
    NcaafTeamInfo("Jacksonville State", "Gamecocks", "JXST", "Conference USA", 55),
    NcaafTeamInfo("Kennesaw State", "Owls", "KENN", "Conference USA", 338),
    NcaafTeamInfo("Liberty", "Flames", "LIB", "Conference USA", 2335),
    NcaafTeamInfo("Middle Tennessee", "Blue Raiders", "MTSU", "Conference USA", 2393),
    NcaafTeamInfo("Missouri State", "Bears", "MOST", "Conference USA", 2623),
    NcaafTeamInfo("New Mexico State", "Aggies", "NMSU", "Conference USA", 166),
    NcaafTeamInfo("Sam Houston", "Bearkats", "SHSU", "Conference USA", 2534),
    NcaafTeamInfo("Western Kentucky", "Hilltoppers", "WKU", "Conference USA", 98),
    NcaafTeamInfo("Notre Dame", "Fighting Irish", "ND", "Independent", 87),
    NcaafTeamInfo("UConn", "Huskies", "CONN", "Independent", 41),
    NcaafTeamInfo("Akron", "Zips", "AKR", "MAC", 2006),
    NcaafTeamInfo("Ball State", "Cardinals", "BALL", "MAC", 2050),
    NcaafTeamInfo("Bowling Green", "Falcons", "BGSU", "MAC", 189),
    NcaafTeamInfo("Buffalo", "Bulls", "BUF", "MAC", 2084),
    NcaafTeamInfo("Central Michigan", "Chippewas", "CMU", "MAC", 2117),
    NcaafTeamInfo("Eastern Michigan", "Eagles", "EMU", "MAC", 2199),
    NcaafTeamInfo("Kent State", "Golden Flashes", "KENT", "MAC", 2309),
    NcaafTeamInfo("Massachusetts", "Minutemen", "MASS", "MAC", 113),
    NcaafTeamInfo("Miami (OH)", "RedHawks", "M-OH", "MAC", 193),
    NcaafTeamInfo("Ohio", "Bobcats", "OHIO", "MAC", 195),
    NcaafTeamInfo("Sacramento State", "Hornets", "SAC", "MAC", 16),
    NcaafTeamInfo("Toledo", "Rockets", "TOL", "MAC", 2649),
    NcaafTeamInfo("Western Michigan", "Broncos", "WMU", "MAC", 2711),
    NcaafTeamInfo("Air Force", "Falcons", "AF", "Mountain West", 2005),
    NcaafTeamInfo("Hawai'i", "Rainbow Warriors", "HAW", "Mountain West", 62),
    NcaafTeamInfo("Nevada", "Wolf Pack", "NEV", "Mountain West", 2440),
    NcaafTeamInfo("New Mexico", "Lobos", "UNM", "Mountain West", 167),
    NcaafTeamInfo("North Dakota State", "Bison", "NDSU", "Mountain West", 2449),
    NcaafTeamInfo("Northern Illinois", "Huskies", "NIU", "Mountain West", 2459),
    NcaafTeamInfo("San José State", "Spartans", "SJSU", "Mountain West", 23),
    NcaafTeamInfo("UNLV", "Rebels", "UNLV", "Mountain West", 2439),
    NcaafTeamInfo("UTEP", "Miners", "UTEP", "Mountain West", 2638),
    NcaafTeamInfo("Wyoming", "Cowboys", "WYO", "Mountain West", 2751),
    NcaafTeamInfo("Boise State", "Broncos", "BOIS", "Pac-12", 68),
    NcaafTeamInfo("Colorado State", "Rams", "CSU", "Pac-12", 36),
    NcaafTeamInfo("Fresno State", "Bulldogs", "FRES", "Pac-12", 278),
    NcaafTeamInfo("Oregon State", "Beavers", "ORST", "Pac-12", 204),
    NcaafTeamInfo("San Diego State", "Aztecs", "SDSU", "Pac-12", 21),
    NcaafTeamInfo("Texas State", "Bobcats", "TXST", "Pac-12", 326),
    NcaafTeamInfo("Utah State", "Aggies", "USU", "Pac-12", 328),
    NcaafTeamInfo("Washington State", "Cougars", "WSU", "Pac-12", 265),
    NcaafTeamInfo("Alabama", "Crimson Tide", "ALA", "SEC", 333),
    NcaafTeamInfo("Arkansas", "Razorbacks", "ARK", "SEC", 8),
    NcaafTeamInfo("Auburn", "Tigers", "AUB", "SEC", 2),
    NcaafTeamInfo("Florida", "Gators", "FLA", "SEC", 57),
    NcaafTeamInfo("Georgia", "Bulldogs", "UGA", "SEC", 61),
    NcaafTeamInfo("Kentucky", "Wildcats", "UK", "SEC", 96),
    NcaafTeamInfo("LSU", "Tigers", "LSU", "SEC", 99),
    NcaafTeamInfo("Mississippi State", "Bulldogs", "MSST", "SEC", 344),
    NcaafTeamInfo("Missouri", "Tigers", "MIZ", "SEC", 142),
    NcaafTeamInfo("Oklahoma", "Sooners", "OU", "SEC", 201),
    NcaafTeamInfo("Ole Miss", "Rebels", "MISS", "SEC", 145),
    NcaafTeamInfo("South Carolina", "Gamecocks", "SC", "SEC", 2579),
    NcaafTeamInfo("Tennessee", "Volunteers", "TENN", "SEC", 2633),
    NcaafTeamInfo("Texas", "Longhorns", "TEX", "SEC", 251),
    NcaafTeamInfo("Texas A&M", "Aggies", "TA&M", "SEC", 245),
    NcaafTeamInfo("Vanderbilt", "Commodores", "VAN", "SEC", 238),
    NcaafTeamInfo("App State", "Mountaineers", "APP", "Sun Belt", 2026),
    NcaafTeamInfo("Arkansas State", "Red Wolves", "ARST", "Sun Belt", 2032),
    NcaafTeamInfo("Coastal Carolina", "Chanticleers", "CCU", "Sun Belt", 324),
    NcaafTeamInfo("Georgia Southern", "Eagles", "GASO", "Sun Belt", 290),
    NcaafTeamInfo("Georgia State", "Panthers", "GAST", "Sun Belt", 2247),
    NcaafTeamInfo("James Madison", "Dukes", "JMU", "Sun Belt", 256),
    NcaafTeamInfo("Louisiana", "Ragin' Cajuns", "UL", "Sun Belt", 309),
    NcaafTeamInfo("Louisiana Tech", "Bulldogs", "LT", "Sun Belt", 2348),
    NcaafTeamInfo("Marshall", "Thundering Herd", "MRSH", "Sun Belt", 276),
    NcaafTeamInfo("Old Dominion", "Monarchs", "ODU", "Sun Belt", 295),
    NcaafTeamInfo("South Alabama", "Jaguars", "USA", "Sun Belt", 6),
    NcaafTeamInfo("Southern Miss", "Golden Eagles", "USM", "Sun Belt", 2572),
    NcaafTeamInfo("Troy", "Trojans", "TROY", "Sun Belt", 2653),
    NcaafTeamInfo("UL Monroe", "Warhawks", "ULM", "Sun Belt", 2433),
]

_BY_ESPN_ID = {t.espn_id: t for t in TEAMS}
_BY_ABBR = {t.abbreviation: t for t in TEAMS}


def team_by_espn_id(espn_id: int) -> NcaafTeamInfo | None:
    return _BY_ESPN_ID.get(espn_id)


def team_by_abbreviation(abbreviation: str) -> NcaafTeamInfo | None:
    return _BY_ABBR.get(abbreviation)


def teams_in_conference(conference: str) -> list[NcaafTeamInfo]:
    return sorted((t for t in TEAMS if t.conference == conference), key=lambda t: t.name)
