# $Id: $
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""
    This module is for functions that are to be executed on a regular basis
    using the TurboGears scheduler.
"""

import os
import shutil
import logging

from os.path import isdir, realpath, dirname, join, islink
from datetime import datetime
from turbogears import scheduler, config
from sqlobject.sqlbuilder import AND

from bodhi import mail
from bodhi.util import get_age_in_days
from bodhi.model import Release, PackageUpdate

log = logging.getLogger(__name__)

def clean_repo():
    """
    Clean up our mashed_dir, removing all referenced repositories
    """
    log.info("Starting clean_repo job")
    liverepos = []
    repos = config.get('mashed_dir')
    for release in [rel.name.lower() for rel in Release.select()]:
        # TODO: keep the 2 most recent repos!
        for repo in [release + '-updates', release + '-updates-testing']:
            liverepos.append(dirname(realpath(join(repos, repo))))
    for repo in [join(repos, repo) for repo in os.listdir(repos)]:
        if not islink(repo) and isdir(repo):
            fullpath = realpath(repo)
            if fullpath not in liverepos:
                log.info("Removing %s" % fullpath)
                shutil.rmtree(fullpath)
    log.info("clean_repo complete!")

def nagmail():
    """
    Nag the submitters of updates based on a list of queries
    """
    log.info("Starting nagmail job!")

    queries = [
            ('old_testing', PackageUpdate.select(
                                    AND(PackageUpdate.q.status == 'testing',
                                        PackageUpdate.q.request != 'stable'))),
            ('old_pending', PackageUpdate.select(
                                    AND(PackageUpdate.q.status == 'pending',
                                        PackageUpdate.q.request == None))),
    ]

    for name, query in queries:
        for update in query:
            if get_age_in_days(update.date_pushed) > 14:
                if update.nagged.has_key(name) and update.nagged[name]:
                    if (datetime.utcnow() - update.nagged[name]).days < 7:
                        continue # Only nag once a week at most
                log.info("[%s] Nagging %s about %s" % (name, update.submitter,
                                                       update.title))
                mail.send(update.submitter, name, update)
                nagged = update.nagged
                nagged[name] = datetime.utcnow()
                update.nagged = nagged

    log.info("nagmail complete!")


def schedule():
    """ Schedule our periodic tasks """

    # Weekly repository cleanup
    scheduler.add_weekday_task(action=clean_repo,
                               weekdays=range(1,8),
                               timeonday=(0,0))

    # Weekly nagmail
    scheduler.add_weekday_task(action=nagmail,
                               weekdays=range(1,8),
                               timeonday=(0,0))
