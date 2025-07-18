from dash import html, dcc, Output, Input, State, callback
import dash

# List of power rankings articles with embedded Google Docs preview links
power_rankings_articles = [
    {
        "id": "week0_2024",
        "title": "2024 Fantasy Pre-Season Power Rankings",
        "author": "Jon Min Htut",
        "date": "October 27, 2023",
        "doc_url": "https://docs.google.com/document/d/1NlHkwKrMi3HoQE8INIshSshelg_7mDNCxgRohnp4VS8/edit?tab=t.0"
    },
    {
        "id": "week11_2023",
        "title": "2023 Power Rankings - Week 11 (Christmas)",
        "author": "Eren Ucar",
        "date": "December 25, 2022",
        "doc_url": "https://docs.google.com/document/d/11dGfSwIvZdUKtFkMnELWQ3Oqj-bKn_euBfnL452ffuc/preview"
    },
    {
        "id": "week8_2023",
        "title": "Dynasty Power Rankings - Week 8 (New Features)",
        "author": "Eren Ucar",
        "date": "December 5, 2022",
        "doc_url": "https://docs.google.com/document/d/15liZbwuDH_HTB8WQkAZnf62s5AEyETTxualOBbXQzJ4/preview"
    },
    {
        "id": "week7_2023",
        "title": "2023 Power Rankings - Week 7",
        "author": "Jon Min Htut",
        "date": "November 28, 2022",
        "doc_url": "https://docs.google.com/document/d/1BJZhf_DrJFz4snNrzhHuXTmMJ4J1J0a4uTjccBnqbH8/preview"
    },
    {
        "id": "week5_2023",
        "title": "2023 Power Rankings Week 5",
        "author": "Franklin Liou",
        "date": "November 14, 2022",
        "doc_url": "https://docs.google.com/document/d/11xs1F_Br1gouN8IYzkPfw-zo4YsFHFnL8S7m-j8xqqg/preview"
    },
    {
        "id": "week4_2023",
        "title": "2023 Power Rankings - Week 4",
        "author": "Eren Ucar",
        "date": "November 7, 2022",
        "doc_url": "https://docs.google.com/document/d/1rAsR1TeW2M-6Xd4GOwX3NjK-QKqOtd6WYAsefPCNF0M/preview"
    },
    {
        "id": "week3_2023",
        "title": "2023 Power Rankings - Week 3",
        "author": "Jon Min Htut",
        "date": "November 1, 2022",
        "doc_url": "https://docs.google.com/document/d/1BqI5-E2I0f522ZtgVQOaYCsiSfseaVnn90MgP3-T1dQ/preview"
    },
    {
        "id": "week2_2023",
        "title": "2023 Power Rankings - Week 2",
        "author": "Jon Min Htut",
        "date": "October 24, 2022",
        "doc_url": "https://docs.google.com/document/d/1-_UrS_jg0UyTmhj8iZ8KNZEMcUX-L5sOJcQfKEWcz2U/preview"
    },
    {
        "id": "preseason_2023",
        "title": "2023 Pre-Season Power Rankings",
        "author": "Franklin Liou, Eren Ucar",
        "date": "October 19, 2022",
        "doc_url": "https://docs.google.com/document/d/129wihm0-Ix65OcWRPj1DqEAoh2qRB3LT_BoovFbCa88/preview"
    },
]

# Generate the HTML layout for each article
def generate_article_block(article):
    return html.Div([
        html.Div([
            html.H4(
                article["title"],
                id={"type": "article-title", "index": article["id"]},
                style={"cursor": "pointer", "textDecoration": "underline", "color": "#0066cc"}
            ),
            html.P(article["date"], style={"color": "gray", "marginBottom": "10px"}),
            html.P(f"Written By: {article['author']}", style={"color": "gray", "marginBottom": "10px"}),

            html.Div(
                id={"type": "article-content", "index": article["id"]},
                children=[
                    html.Iframe(
                        src=article["doc_url"],
                        width="100%",
                        height="500px",
                        style={"border": "1px solid #ccc", "marginBottom": "40px"}
                    )
                ],
                style={"display": "none"}
            )
        ])
    ])

# Tab layout
def get_power_rankings_layout():
    return html.Div([
        html.H2("Power Rankings"),
        html.P("Click a title below to read the article.", style={"marginBottom": "30px"}),
        dcc.Store(id="open-article-id", data=None),
        *[generate_article_block(article) for article in power_rankings_articles]
    ], style={"padding": "30px"})

def register_power_rankings_callbacks(app):
    @callback(
        Output({"type": "article-content", "index": dash.ALL}, "style"),
        Input({"type": "article-title", "index": dash.ALL}, "n_clicks"),
        State({"type": "article-content", "index": dash.ALL}, "style"),
        prevent_initial_call=True
    )
    def toggle_article_visibility(clicks, styles):
        ctx = dash.callback_context
        if not ctx.triggered:
            return styles

        clicked_id = ctx.triggered[0]["prop_id"].split(".")[0]
        clicked_index = eval(clicked_id)["index"]

        updated_styles = []
        for i, style in enumerate(styles):
            article_id = ctx.inputs_list[0][i]["id"]["index"]
            if article_id == clicked_index:
                # Toggle visibility
                is_visible = style.get("display") != "none"
                updated_styles.append({"display": "none"} if is_visible else {"display": "block"})
            else:
                updated_styles.append({"display": "none"})  # Collapse others

        return updated_styles