from leagueDataUpdater import update_league_data
from playerMatchupDataUpdater import update_playerMatchup_data

def run_all_updates():
    #print("Updating league data...")
    update_league_data()

    #print("Updating player matchup data...")
    update_playerMatchup_data()

    #print("All data updates complete!")

if __name__ == "__main__":
    run_all_updates()