export const TEAM_TABS = [
  {key:'roster',label:'Roster'},
  {key:'rankings',label:'Category Rankings'},
  {key:'weekly',label:'Weekly Performance'},
  {key:'physicals',label:'Physicals'},
];

export const defaultTeamTab=()=>TEAM_TABS[0].key;
export const selectTeamTab=tab=>TEAM_TABS.some(item=>item.key===tab) ? tab : defaultTeamTab();
