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
    "Who Invited This Kid?": "assets/logos/WhoInvitedThisKid.png"
}

# Fallback default
default_logo_path = "assets/logos/Default.png"

def get_logo_path(team_id):
    return f"/{team_logo_paths.get(team_id, default_logo_path)}"