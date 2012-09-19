Duxlot, the IRC Bot
===================

Duxlot_ is a new IRC bot created by `Sean B. Palmer`_, the maker of the popular
Phenny_. Features include a fast multiprocess architecture, modularity, and
ease of use. Duxlot has no dependencies except Python 3, and will even work
without having to be installed as as package.

.. _Duxlot: http://inamidst.com/duxlot/
.. _Sean B. Palmer: http://inamidst.com/sbp/
.. _Phenny: http://inamidst.com/phenny/

Install
---------

    **WARNING:** This is an pre-release alpha version of Duxlot. The API and
    features may change, and the bot may not be stable.

Get `Python 3.2`_ or later.

.. _Python 3.2: http://www.python.org/download/releases/3.2.3/

You may use **either** of these methods:

*   Download the latest source:

        `duxlot-0.9.19-1542.tar.bz2`_

    Unpack it and enter ``duxlot-0.9.19-1542/``

    **Optionally** install using::

        python3 setup.py install

.. _duxlot-0.9.19-1542.tar.bz2: http://pypi.python.org/packages/source/d/duxlot/duxlot-0.9.19-1542.tar.bz2

*	OR: Install from pypi_ using pip_::

		pip install duxlot

.. _pypi: http://pypi.python.org/
.. _pip: http://pypi.python.org/pypi/pip

**Optionally** use virtualenv_ for either of these methods.

.. _virtualenv: http://www.virtualenv.org/en/latest/index.html#installation

You can now use the ``duxlot`` script—either the one in the package that you
downloaded, or the one that should be on your ``$PATH`` from installation.

Use
---

	**WARNING:** The entire Duxlot API is not yet stable, including the
	configuration file. Early adopters will find themselves having to change
	the configuration files often, with undocumented changes occurring.

Duxlot works by loading a JSON_ configuration file specified by the user. To
create a default configuration file with some options filled in to work from,
do::

	duxlot create

.. _JSON: https://en.wikipedia.org/wiki/JSON

This will create a file at ``~/.duxlot/duxlot.json``, which is the **default
configuration file**. You can also create this file manually, if you prefer.
You can then edit the file with various options recognised by Duxlot. Here's an
example::

	{
	    "address": "barjavel.freenode.net:6667",
	    "nick": "duxlot001",
	    "prefix": "^",
	    "admin-owner": "you",
	    "start-channels": ["#duxlot-test"]
	}

A summary of all allowed options is given in the section below.

You can then run the bot either as a daemon_::

	duxlot start

.. _daemon: https://en.wikipedia.org/wiki/Daemon_(computing)

Or in the foreground::

	duxlot --foreground start

If you run the bot as a daemon, you will be told the PID_ of the daemon. You
can stop the bot using the stop action::

	duxlot stop

.. _PID: https://en.wikipedia.org/wiki/Process_identifier

Or by sending a SIGTERM signal_ to the PID manually.

.. _signal: http://en.wikipedia.org/wiki/Unix_signal

To find out what else the ``duxlot`` script can do, try these commands::

	duxlot --help
	duxlot --usage

Options
---------------------

These are the allowed option fields for the configuration file:

:address: Server to connect to, as "[ssl ]<hostname>[:<port>]"
:nick: Nick for the bot to use for itself
:prefix: Default prefix used across all channels for commands

:admin-channels: Channels in which some admin commands can be used
:admin-owner: Owner of the bot, allowed to use owner commands
:admin-users: Users who are allowed to use admin commands

:core-private: Private channels where seen data should not be recorded

:start-channels: List of channels to join on connecting to the server
:start-nickserv: Password to send to the NickServ services bot
:start-password: Password to send to the server

Story
-----

People love Phenny, the predecessor of Duxlot. Some of them have wondered how
Duxlot relates to Phenny. Stay tuned for information!

Pronunciation
-------------

Duxlot is pronounced djuːksləʊ, or dʌksləʊ, in IPA_.

.. _IPA: https://en.wikipedia.org/wiki/International_Phonetic_Alphabet

Credits
-------

* David P. Kendal (@dpkendal), who helped me to debug
* Smedley Butler (@epivalent), who helped me to maintain bug isostasy
* Björn Höhrmann (@hoehrmann), who confused me into adding bugs
