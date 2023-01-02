# Projekt Internet Of Things

## Połączenie z urządzeniem (serwerem OPC UA)
Do połączenia z agentem wykorzystywana jest biblioteka **asyncua**. Połączenie następuje po uruchumioniu programu w pliku `main.py`. Adres serwera pobierany jest z pliku `config.ini`.

Przykładowy plik `config.ini`
```ini
[server]
url = opc.tcp://192.168.1.100:4840
```

## Konfiguracja agenta
Konfiguracja agenta następuje po połączeniu z serwerem. Dla każdego urządzenia powstaje osobny agent. Po połączeniu z serwerem pobierana jest lista dostępnych urządzeń, nas†epnie, każde urządzenie (klasa Node z biblioteki **asyncua**) wraz z jego `connection_string` i klientem OPC UA jest przekazywana jako argument podczas tworzenia instancji klasy `Agent`.

Connection stringi dla każdego urządzenia są przechowywane w pliku konfiguracyjnym:
```ini
[devices]
device 1 = <connection_string>
device 2 = <connection_string>
```

Kod opisany powyżej:
```python
async with Client(config.get_server_url()) as client:
  objects = client.get_objects_node()
  for device in await objects.get_children():
      device_name = (await device.read_browse_name()).Name
      if device_name != 'Server':
          agent = await Agent(
              device=device,
              connection_string=config.get_device_config(device_name),
              opcua_client=client
          ).create()

          agents.append(agent)
```

## Rodzaj, format i częstotliwość wiadomości (D2C messages)
Wiadomości wysyłane do IoT Huba przez agenta to:
- telemetria
- informacja o wystąpieniu zdarzenia

Agent wysyła informacje co 1 sekundę.

Format wiadomości:
```json
// telemetria
{
  "body": {
    "ProductionStatus": 1,
    "WorkorderId": "80cff94a-f588-48f4-b54e-410fe0230979",
    "GoodCount": 42,
    "BadCount": 8,
    "Temperature": 69.06253498503816,
    "MessageType": "Telemetry"
  },
  "enqueuedTime": "Mon Jan 02 2023 22:43:28 GMT+0100 (Central European Standard Time)",
  "properties": {}
}
```

```json
// informacja o wystąpieniu zdarzenia
{
  "body": {
    "DeviceError": "Power Failure",
    "MessageType": "Event"
  },
  "enqueuedTime": "Mon Jan 02 2023 22:43:29 GMT+0100 (Central European Standard Time)",
  "properties": {}
}
```

## Rodzaj i format danych przechowywanych w Device Twin
W Device Twin przechowywane są następujące informacje: `Reported Production Rate`, `Reported Device Error`, `MaintenanceDone`, `LastErrorDate`, `MaintenanceDone`, `Desired Production Rate`.

Przykładowy Device Twin:
```json
{
	"deviceId": "device1",
	"etag": "AAAAAAAAAAQ=",
	"deviceEtag": "OTA4NTk1Mjg=",
	"status": "enabled",
	"statusUpdateTime": "0001-01-01T00:00:00Z",
	"connectionState": "Disconnected",
	"lastActivityTime": "2023-01-02T21:43:41.2182189Z",
	"cloudToDeviceMessageCount": 0,
	"authenticationType": "sas",
	"x509Thumbprint": {
		"primaryThumbprint": null,
		"secondaryThumbprint": null
	},
	"modelId": "",
	"version": 26,
	"properties": {
		"desired": {
			"ProductionRate": 17,
			"$metadata": {
				"$lastUpdated": "2023-01-02T21:42:14.7050295Z",
				"$lastUpdatedVersion": 4,
				"ProductionRate": {
					"$lastUpdated": "2023-01-02T21:42:14.7050295Z",
					"$lastUpdatedVersion": 4
				}
			},
			"$version": 4
		},
		"reported": {
			"MaintenanceDone": "2023-01-02T22:21:20.255188",
			"ProductionRate": 30,
			"DeviceError": [
				"Power Failure",
				"Sensor Failure"
			],
			"LastErrorDate": "2023-01-02T22:43:31.548593",
			"$metadata": {
				"$lastUpdated": "2023-01-02T21:43:31.7177262Z",
				"MaintenanceDone": {
					"$lastUpdated": "2023-01-02T21:21:20.314905Z"
				},
				"ProductionRate": {
					"$lastUpdated": "2023-01-02T21:43:25.4205283Z"
				},
				"DeviceError": {
					"$lastUpdated": "2023-01-02T21:43:31.7177262Z"
				},
				"LastErrorDate": {
					"$lastUpdated": "2023-01-02T21:43:31.5614704Z"
				}
			},
			"$version": 22
		}
	},
	"capabilities": {
		"iotEdge": false
	}
}
```

## Direct Methods
Agent obsługuję wbudowane w urządzenie metody takie jak: `EmergencyStop`, `ResetErrorStatus` oraz dodatkową metodę `MaintenanceDone`.

Metody te nie przyjmują żadnych parametrów oraz nie zwracają żadnych informacji poza statusem powodzenia (status 200) oraz informacją o nazwie metody jaka została wykonana. W przypadku próby wykonania nie istniejącej metody dostaniemy informacje o tym, że owa metoda nie istnieje ze statusem 404.

## Sposób zaimplementowania kalkulacji i logiki biznesowej
### Kalkulacje
Wszystkie kalkulacje zachodzą w chmurzę przy wykorzystaniu kwerend w Azure Stream Analytics job. Wyniki kwerend są przechowywane przy pomocy blobów w Storage Account.

Wykorzystane do kalkulacji kwerendy:
```sql
-- production kpi w 15 minutowym okienku
select
    DateAdd(minute,-15,System.Timestamp()) as StartTimestamp,
    System.Timestamp() as EndTimestamp,
    IoTHub.ConnectionDeviceId as DeviceId,
    Sum(GoodCount) * 100 / (Sum(GoodCount) + Sum(BadCount)) as ProductionKpi
into [kpi-blob]
from [iot-in]
where MessageType = 'Telemetry'
group by IoTHub.ConnectionDeviceId, TumblingWindow(minute, 15);

--temperatura w okienku 5 minutowym
select
    DateAdd(minute,-5,System.Timestamp()) as StartTimestamp,
    System.Timestamp() as EndTimestamp,
    IoTHub.ConnectionDeviceId as DeviceId,
    Max(Temperature) as max,
    Min(Temperature) as min,
    Avg(Temperature) as avg
into [temperature-blob]
from [iot-in]
where MessageType = 'Telemetry'
group by IoTHub.ConnectionDeviceId, TumblingWindow(minute, 5);

--błędy w okienku 30 minutowym
select
    DateAdd(minute,-30,System.Timestamp()) as StartTimestamp,
    IoTHub.ConnectionDeviceId as DeviceId,
    Count(error) as errorCount
into [error-30-blob]
from [iot-in]
where MessageType = 'Event'
group by IoTHub.ConnectionDeviceId, TumblingWindow(minute, 30);

--suma good i bad count per workorder id
select
    WorkorderId,
    Max(GoodCount) as Good,
    Max(BadCount) as Bad
into [production-blob]
from [iot-in]
where MessageType = 'Telemetry'
group by WorkorderId, SessionWindow(minute, 2, 1440);
```

### Logika biznesowa
Obliczenia potrzebne do monitorowania i zastosowania logiki biznesowej są również wykonywane po stronie Azure Stream Analytics. Natomiast w tym przypadku outputem nie jest już blob, a Function App.

Kwerendy dla logiki biznesowej:
```sql
--błędy w okienku 15 minutowym
select
    IoTHub.ConnectionDeviceId as DeviceId,
    count(*) as ErrorCounts
into [emergency-stop-handler]
from [iot-in]
where MessageType = 'Event'
group by IoTHub.ConnectionDeviceId, SlidingWindow(minute, 15)
having count(*) > 3;

--production kpi w okienku 15 minutowym (dla funkcji)
select
    DateAdd(minute,-15,System.Timestamp()) as StartTimestamp,
    System.Timestamp() as EndTimestamp,
    IoTHub.ConnectionDeviceId as DeviceId,
    Sum(GoodCount) * 100 / (Sum(GoodCount) + Sum(BadCount)) as ProductionKpi
into [production-rate-kpi-handler]
from [iot-in]
where MessageType = 'Telemetry'
group by IoTHub.ConnectionDeviceId, TumblingWindow(minute, 15);
```