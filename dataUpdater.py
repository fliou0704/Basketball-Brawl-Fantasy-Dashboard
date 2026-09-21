from leagueDataUpdater import update_league_data
from playerMatchupDataUpdater import update_playerMatchup_data
from playerDailyDataUpdater import update_player_daily_data
from scripts.generate_scoring_period_map import generate as generate_scoring_period_map

def run_all_updates():
    #print("Updating league data...")
    update_league_data()

    #print("Updating player matchup data...")
    update_playerMatchup_data()

    #print("Updating player daily data...")
    update_player_daily_data()

    # Keep the explicit ESPN scoring-period reference in sync with the saved
    # season metadata used by the exporters.
    generate_scoring_period_map()

    #print("All data updates complete!")

if __name__ == "__main__":
    run_all_updates()
