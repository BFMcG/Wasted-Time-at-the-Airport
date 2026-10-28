CREATE OR REPLACE VIEW flights.airlines as
SELECT airline_code, airline_name
FROM (
    VALUES
        ('SWA', 'Southwest'),
        ('ASA', 'Alaska/Horizon'),
        ('QXE', 'Alaska/Horizon'),
        ('SKW', 'SkyWest'),
        ('UAL', 'United'),
        ('AAL', 'American'),
        ('DAL', 'Delta'),
        ('FFT', 'Frontier'),
        ('JBU', 'JetBlue')
) as t (airline_code, airline_name)