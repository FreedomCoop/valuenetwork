# Add a Faircoin Wallet service:

- Install the last ElectrumFair wallet from https://download.faircoin.world : ::

        sudo pip3 install https://download.faircoin.world/electrum/ElectrumFair-3.0.5.tar.gz
        sudo pip install jsonrpclib

- Create an electrumfair wallet: ::

        electrumfair create

This gives you seed to keep in safe place, and ask for password to encript the wallet.
All the electrumfair data will be created in /home/user/.electrumfair/ directory.
Be carefull if you already have an electrum-fair wallet installed with the same user.

- Once the OCP is downloaded from github, enter its root folder and copy the
daemon sample files: ::

        cp faircoin/daemon/daemon_service.sample faircoin/daemon/daemon_service
        chmod a+x faircoin/daemon/daemon_service
        cp faircoin/daemon/daemon.py.sample faircoin/daemon/daemon.py
        chmod a+x faircoin/daemon/daemon.py
        cp faircoin/daemon/daemon.conf.sample faircoin/daemon/daemon.conf

- Setup daemon: ::

        vim faircoin/daemon/daemon_service #Set paths and user for starting the daemon.
        vim faircoin/daemon/daemon.conf #Set wallet config
        sudo ./faircoin/daemon/daemon_service start
        sudo ./faircoin/daemon/daemon_service status

If daemon runs ok, *daemon_service status* returns *Running*.
For ocp instances in production, better to move daemon_service to */etc/init.d/* and daemon.conf to */etc/*

- The local_settings PROJECTS_LOGIN object for the project should have the 
'faircoin' as an active service.

- There's an OCP page to overview all assigned accounts of the server wallet at '.../faircoin/faircoin-checking'
