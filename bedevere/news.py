"""Check for a news entry."""
import functools
import pathlib
import re

import gidgethub.routing

from . import util


router = gidgethub.routing.Router()


create_status = functools.partial(util.create_status, 'bedevere/news')

BLURB_IT_URL = 'https://blurb-it.herokuapp.com'

FILENAME_RE = re.compile(r"""# YYYY-mm-dd or YYYY-mm-dd-HH-MM-SS
                             \d{4}-\d{2}-\d{2}(?:-\d{2}-\d{2}-\d{2})?\.
                             bpo-\d+(?:,\d+)*\.       # Issue number(s)
                             [A-Za-z0-9_=-]+\.        # Nonce (URL-safe base64)
                             rst                      # File extension""",
                         re.VERBOSE)

SKIP_NEWS_LABEL = util.skip_label("news")
SKIP_LABEL_STATUS = create_status(util.StatusState.SUCCESS,
                                  description='"skip news" label found')


async def check_news(gh, pull_request, files=None):
    """Check for a news entry.

    The routing is handled through the filepaths module.
    """
    if not files:
        files = await util.files_for_PR(gh, pull_request)
    in_next_dir = file_found = False
    for file in files:
        if not util.is_news_dir(file['file_name']):
            continue
        in_next_dir = True
        file_path = pathlib.PurePath(file['file_name'])
        if len(file_path.parts) != 5:  # Misc, NEWS.d, next, <subsection>, <entry>
            continue
        file_found = True
        if FILENAME_RE.match(file_path.name) and len(file['patch']) >= 1:
            status = create_status(util.StatusState.SUCCESS,
                                   description='News entry found in Misc/NEWS.d')
            break
    else:
        issue = await util.issue_for_PR(gh, pull_request)
        if util.skip("news", issue):
            status = SKIP_LABEL_STATUS
        else:
            if not in_next_dir:
                description = f'No news entry in {util.NEWS_NEXT_DIR} or "skip news" label found'
            elif not file_found:
                description = "News entry not in an appropriate directory"
            else:
                description = "News entry file name incorrectly formatted"
            status = create_status(util.StatusState.FAILURE,
                                   description=description,
                                   target_url=BLURB_IT_URL)

    await gh.post(pull_request['statuses_url'], data=status)


@router.register('pull_request', action="labeled")
async def label_added(event, gh, *args, **kwargs):
    if util.label_name(event.data) == SKIP_NEWS_LABEL:
        await util.post_status(gh, event, SKIP_LABEL_STATUS)


@router.register("pull_request", action="unlabeled")
async def label_removed(event, gh, *args, **kwargs):
    if util.no_labels(event.data):
        return
    elif util.label_name(event.data) == SKIP_NEWS_LABEL:
        pull_request = event.data['pull_request']
        await check_news(gh, pull_request)
