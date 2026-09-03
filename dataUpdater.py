from leagueDataUpdater import update_league_data
from playerMatchupDataUpdater import update_playerMatchup_data
from playerDailyDataUpdater import update_player_daily_data

def run_all_updates():
    #print("Updating league data...")
    update_league_data()

    #print("Updating player matchup data...")
    update_playerMatchup_data()

    #print("Updating player daily data...")
    update_player_daily_data()

    #print("All data updates complete!")

if __name__ == "__main__":
    run_all_updates()
