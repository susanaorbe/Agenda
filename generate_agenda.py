from renderer import generate_html
from scrapers import (
    fetch_and_parse_agenda,
    fetch_sport_tv_guide_favorite_events,
    update_channels_json_from_api,
)


def main():
    update_channels_json_from_api()
    agenda_events = fetch_and_parse_agenda()
    stg_events = fetch_sport_tv_guide_favorite_events()
    final_html = generate_html(agenda_events, stg_events)
    with open("index.html", "w", encoding="utf-8") as out_f:
        out_f.write(final_html)
    print("index.html generado correctamente.")


if __name__ == "__main__":
    main()