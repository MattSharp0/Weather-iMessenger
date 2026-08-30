# Weather-Messenger

## Usage Flow

### Initial setup

1.  Admin of tool logs in and adds a phone number to the application and it is stored as unverified in SQLite db. This can be done via CLI or web page, whichever is simpler to build. As this is only designed to work for me / my partner / select friends, CLI seems easiest since security can be handled via host service.
2.  Application sends an iMessage OTP to this number
3.  User enters OTP, application then updates this number to be 'Verified' in db. This number is now capable of sending coordinates for weather forecast requests.

### Regular usage

1.  An iMessage is sent containinng coordinates
2.  Application checks phone number has been previously verified with the application. If not on verified no response is sent
3.  If valid phone number, application parses coordinates
4.  Coordinates are used to query weather forecast via Open Meteo or Weather.gov
5.  Weather summary (text only) is sent back via iMessage

## Build info

- Language: Python (manage via UV)
- Databse: SQLite (see schema.sql
- Flask or FastAPI framework?
