import pandas as pd

data = pd.read_csv("data/basketballBrawlLeagueData.csv")

# Create a dictionary mapping team IDs to logo file paths
team_logo_paths = {
    "For All the bullDawgs": "assets/logos/ForAllthebullDawgs.png",
    "I Watch Basketbal": "assets/logos/IWatchBasketbal.png",
    "Keegan It Real": "assets/logos/KeeganItReal.png",
    "New Jersey Eren": "assets/logos/NewJerseyEren.png",
    "NYC Chopp Cheese": "assets/logos/NYCChoppCheese.png",
    "Paulie Gee's": "assets/logos/PaulieGees.png",
    "Pooh Shaisty": "assets/logos/PoohShaisty.png",
    "Team Chigga": "assets/logos/TeamChigga.png",
    "The Bronx Orthodox Church": "assets/logos/TheBronxOrthodoxChurch.png",
    "Who Invited This Kid?": "assets/logos/WhoInvitedThisKid.png",
    "NY L-Eat Gang": "assets/logos/NYL-EatGang.png",
    "Fordham Rams": "assets/logos/NYCChoppCheese.png",
    "Jalen Inc.": "assets/logos/NYCChoppCheese.png"
}

# Fallback default
default_logo_path = "assets/logos/Default.png"

team_colors = {
    1: "#41ade3",  # Keegan It Real
    2: "#4636c6",  # New Jersey Eren
    5: "#f7941c",  # Team Chigga
    7: "#ffdb00",  # Who Invited This Kid?
    8: "#875b1a",  # Paulie Gee's
    10: "#b99f87",  # For All the bullDawgs
    12: "#a42868",  # Pooh Shaisty
    13: "#900b1d",  # The Bronx Orthodox Church
    16: "#d62628",  # Jalen Inc.
    17: "#46424b",  # I Watch Basketbal
}

default_color = "#228B22"

def get_logo_path(team_name):
    return f"/{team_logo_paths.get(team_name, default_logo_path)}"

def get_team_color(team_id):
    return team_colors.get(team_id, default_color)