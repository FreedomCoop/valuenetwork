<!-- ABOUT THE PROJECT -->
## Open Collaborative Platform

OCP is a collective economic management platform, based on the [REA](https://en.wikipedia.org/wiki/Resources,_events,_agents_(accounting_model)) accounting model (Resource-Event-Agent), which allows for a common 'economic facts tracking system' used among the projects and users using the platform (the economic Agents). Accounting any kind of resource in this multi-context system can help to a more ethical and efficient economic system.

OCP was born as a fork from the ValueNetwork NRP (Network Resource Planning) by mikorizal.org in June 2016 to solve the needs of FreedomCoop (by FairCoop), using FairCoin as the main internal currency, and also to pay the Shares at membership time.

Since then, the OCP has been refactored into a multi-context system, where various projects with different domains and urls can use the same backend and share a common database with many common data (agents, units, resource types, etc) but having each context their own register process, their own payment gateways, active services, email notification server, and a long etc.

FairCoop itself, to track tasks and distributions (OCW) used OCP as the backend for the [Agent](https://github.com/opencooperativeecosystem/agent) react frontend, based also on the [ValueFlows](https://valueflo.ws) vocabulary.

Bank of the Commons is a big main project that started to use OCP for their whole membership process and shares system (launched on June 2017), and some payment gateways has been implemented ad-hoc for them, and also the 'multicurrency' app that allows each user to create/access their BotC multi-wallet from the OCP. 

The initial readme said:
REA is an Accounting in a large sense. The idea behind this app is "something analogous to an ERP system for value networks. Might call it NRP for Network Resource Planning or OCP for Open Collaborative Platform".


## Features
* Multi-language platform (static texts)
* Multi-language international projects (dynamic db texts):
	- Translatable agent fields: name, nickname, email, website, address, description, phone and image url.
	- Translatable agent's relation type fields: name, plural name, label and inverse label.
	- Translatable resource type fields: name and description.
	- Translatable agent-resource role 'name' field.
	
* Custom register form fields and texts for each project (using fobi).
* Custom register joining style per project:
	- 'autojoin' (for internal projects, just click to join, no moderation)
	- 'moderated' (review and communication for each candidature, needs custom fobi form)
	- 'shares' (moderated but involving project's shares and payment gateways)
	- 'subscription' (still WIP)
* Custom project visibility: public, private or FCmembers
* Custom membership workflow boolean option for moderated projects: 
	- Auto create user+agent and send confirm email: to review manually the spam registers before even sending the confirm email (with a usable password) leave unchecked. To speedup the process if you don't expect much spam, check it.
* Custom domain urls configurable for each main project context to access OCP.
	* Custom login and register texts for each main project.
	* Custom CSS, Javascript and background image for each main project.
	* Custom active services per main project, the options are:
		- faircoins (enables the internal faircoin wallet connection)
		- multicurrency (enables the BotC wallet connection)
        - projects (allows project's members to manage other projects in OCP)
		- shares (enables the project's custom shares management)
        - exchanges (enables the 'exchanges' view of the economic transfers)
		- skills (enables skills management for project's members)
        - tasks (enables the tasks system for members)
        - processes (enables the plan/process system for members)

* Custom Share definition and value per project (if needed):
	- Share's name, shortname, value-unit (Eur, Fair, Btc, etc) and unit-value (share's price).
* Custom Payment gateways per project (to pay their shares):
	- Bank Transfer, or any manual confirmation option.
	- Faircoin using the internal server wallet to pay from the user's fair-account to the project's account (auto confirms on pay).
	- Faircoin using the BotC multiwallet (to confirm payments the coordinators must put the corresponding BotC-Wallet transaction ID and the received amount).
	- Faircoin using an external project's fair-account (to confirm payments the coordinators must put the corresponding blockchain tx hash and the exact received amount).
	- BTC or ETH using an external project's btc or eth account (to confirm payments the coordinators must put the corresponding blockchain tx hash and the exact received amount).
	- CreditCard synchronous gateway was ready using the Fairbill processor service, and it autoconfirmed the payments correctly, but has never been used in production yet.

* Join Requests page for project's coordinators to manage the candidatures:
	- Fast page load for big projects, using ajax pagination with DataTables.
	- Easy buttons that appears when needed to: 
		- send the confirm email (with the user initial random password) if is pending, 
		- delete all (request, user and agent) when email not confirmed for long time,
		- go to the feedback page with the candidate (shows nº of comments), 
		- go to the exchange page related the shares purchase (or set as pending if the exchange is missing), 
		- accept the member, if shares it shows-up when payed (will activate the member access to the project's offered tools) 
		- decline the candidature (inactivates the member access to the project's tools),
* Feedback page related any moderated membership process with any project. it shows:
	- The data entered by the user in the project's register form.
	- The custom form fields of any candidate's join-request answers can be edited by the coordinators of the project (just click on them).
	- If shares, to help the candidate to do the payment depending on her/his chosen payment gateway:
		- if chosen Faircoin from the internal faircoin wallet accounts, a button to pay appears if enough balance, or useful warning info instead.
		- if chosen bank Transfer or any manual option, the details to pay are shown. Coordinators can manually confirm the payment to setup the exchange as complete.
		- if chosen other Cryptos using external accounts, the info to pay is shown for candidates. Coordinators will need to input the blockchain transaction hash and the exact received amount (9 decimals).
		- if chosen Faircoin from the BotC-Wallet account: if the candidate has filled-up a special 'multicurrency username' field in the register form, the multicurrency Connect button appears, otherwise a 'Create Multicurrency Account' button appears. 

* Exchanges page to represent each agent economic activity related other agents (buys/sells of resources or services, etc), with:
	- a flexible multi-unit Totals box, which shows actual balances and also commited future balances, related the commitments in the exchanges related the user. The calculated balances are now cached to gain speed on page load.
	- a simplified Filters box, which filters by dates range, by state and by types, now all via ajax (without reloading the page).
	- a fast paginated ajax list of Exchanges, representing in each row the main information useful for the user, showing both transfers of any exchange (except for donations, which has one transfer), using the js DataTables plugin.

* Many more features inherited from the original valuenetwork: Simple tasks and process tasks, plan a process with or without using known 'recipes',
value equations and distributions, etc.


### Built With
* [Python](https://www.python.org/)
* [Django](https://www.djangoproject.com/)
* [Pinax](https://pinaxproject.com/)
* [Fobi](https://github.com/barseghyanartur/django-fobi/)
* [jQuery]()
* [DataTables]()
* [Bootstrap]()
* ...


## Release v1.0.0
- Python 3.7 compatible, works with Django 2.0 (see other updates in 'requirements.txt')
- Uses the NPM build system to work from scss files (still only used by the new pinax template)
- jQuery 3.3, Bootstrap 4.0, and other updates seen in `package.json`

### Fixes 

- Fixed the speed issues for coordinators of large projects, by post-loading of data via ajax paginated chunks, in the most critital management pages:
	- the Join Requests list page
	- the Project's page, now the Relations box will load users in the lists only if you open them, and by small chunks.
	- the Exchanges list page
- Fixed the unit tests to re-enable the Travis-CI green check:
	- The selenium tests are working again with a particular chromedriver version (see note).
	- The API tests were repaired by refactoring to Python3, Graphql2, upgrading graphene, etc.
- Fixed many Responsive issues, now is usable from small devices.
- Fixed the main Install doc and other docs (at `/docs`) and this Readme.

<!-- GETTING STARTED -->
### Installation
To get a local copy up and running follow these simple steps: [Install](../INSTALL.md)

<!-- USAGE EXAMPLES -->
## Usage
Some working urls using the actual OCP platform instances are:
- https://members.bankofthecommons.coop
- https://ocp.freedomcoop.eu
- https://join.integral.tools

## Docs 
see a bit of [Bank of the Commons OCP History](https://github.com/FreedomCoop/valuenetwork/wiki/Bank-of-the-Commons---OCP-History)

<!-- ROADMAP -->
## Roadmap of the Dev Team

- Maintenance and stabilization of OCP 1.x version by fixing any found bug and improve overall usability for the main projects using the platform. Clean old unused code and better self document the code in-place.

- Find ways to keep funding the maintenance and features development.

- Find ways to involve more developers.

- Find ways to increase the early testers team and overall community around the software.

- Finish the recurring payments 'subscription' model membership workflow.

- Milestone #1: Create a new React Frontend learning from the [Shroom](https://github.com/ivanminutillo/shroom) and the 'Agent' expereinces to allow:
	- an easy input of user Needs, starting with Food needs, and
	- an easy input of user offered Food products for producers and consumer groups. 
	- This frontend will be initially connected to the OCP as a backend, but will be also useful for the future [CommonDB](https://commondb.net) distributed data network backend.

- Milestone #2: Port all the actual membership and exchanges functionality to the new react frontend, at least for regular members.
- Other possible milestones:
  - Port to the new react frontend:
    - all other OCP features (faircoins, multicurrency, skills, tasks and process, etc)
    - port also the project's coordinators pages and tools
  - If the BotC multiwallet service becomes too old or unstable, and there is enough team and funds in OCP:
    - build a BTC and a ETH wallets in the ocp server and connect each user with an account, like we do with Faircoin, to allow direct multicurrency from OCP internally


<!-- CONTRIBUTING -->
## Contributing [![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/dwyl/esta/issues)

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Contributors
see [Contributors.txt](../CONTRIBUTORS.txt)

<!-- LICENSE -->
## License

<!-- CONTACT -->
## Contact

[![Gitter](https://badges.gitter.im/OpenCollaborativePlatform/community.svg)](https://gitter.im/OpenCollaborativePlatform/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)



Donations: 


<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements
* ![Bank of the Commons](https://bankofthecommons.coop/img.png)
* ![Freedomcoop](http://url/to/img.png)
* ![FairCoop](http://url/to/img.png)
* ![SynergieHub](http://url/to/img.png)
* ![Sporos](http://url/to/img.png)
