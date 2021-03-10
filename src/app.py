import json
import locale
import logging
import sys
from pathlib import Path

from pydiscourse.exceptions import DiscourseClientError
from pydiscourse import DiscourseClient
from constants import DISCOURSE_CREDENTIALS

locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")


def check_login(client: DiscourseClient) -> None:
    try:
        client.latest_topics()
    except DiscourseClientError as e:
        logging.error(f"Could not perform login: {e}")
        sys.exit(-1)


def send_ballot(client, username):
    res = client.create_post("huhu", title="Testabstimmung y", archetype="private_message",
                             target_usernames=username)
    return res.get('topic_id')


def get_vote(client, topic_id):
    posts = client.topic_posts(topic_id)["post_stream"]["posts"]
    for post in posts:
        print(post["cooked"])


def initiate_election(client: DiscourseClient, users=None):
    if not users:
        users = client.users()
        with open("users.json", "w") as f:
            json.dump(users, f)
    topics = []
    for user in users:
        if not user["active"] or "suspended_at" in user:
            continue
        if user["username"] not in ["soerface", "anselm"]:
            continue
        topics.append(send_ballot(client, user["username"]))

    with open("topics.json", "w") as f:
        json.dump(topics, f)


def get_election_results(client: DiscourseClient):
    with open("topics.json") as f:
        topics = json.load(f)
    for topic_id in topics:
        get_vote(client, topic_id)


if __name__ == "__main__":
    client = DiscourseClient(**DISCOURSE_CREDENTIALS)
    check_login(client)
    users_json = Path("users.json")
    if users_json.exists():
        with open(users_json) as f:
            users = json.load(f)
    else:
        users = None
    initiate_election(client, users=users)
    get_election_results(client)
