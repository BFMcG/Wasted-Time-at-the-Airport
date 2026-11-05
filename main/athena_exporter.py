import time

class AthenaExporter:
    def __init__(self, athena_client, workgroup, database,
                 poll_seconds=1, poll_timeout=30):
            self.athena_client = athena_client
            self.workgroup = workgroup
            self.database = database
            self.poll_seconds = poll_seconds
            self.poll_timeout = poll_timeout

    def start_query(self, sql) -> str:
         '''
         Getting query execution id from Athena given SQL query.
         '''
         response = self.athena_client.start_query_execution(
               QueryString=sql,
               QueryExecutionContext={'Database': self.database},
               WorkGroup=self.workgroup
            )

         return response['QueryExecutionId']

    def wait_for_query(self, query_id) -> None:
        '''
        Check status of query every second until 
        a state is reached, or until timed out.
        '''
        time_out = time.monotonic() + self.poll_timeout
        while True:
            response = self.athena_client.get_query_execution(
                QueryExecutionId=query_id
            )
            state = response['QueryExecution']['Status']['State']
            if state == 'SUCCEEDED':
                return None
            elif state in ['FAILED', 'CANCELLED']:
                raise RuntimeError(f"Query {state} reason: "
                                   f"{response['QueryExecution']['Status'].get('StateChangeReason')}")
            time.sleep(self.poll_seconds)
            if time.monotonic() > time_out:
                raise TimeoutError(f"Query took longer than {self.poll_timeout} "
                                   f"seconds to complete, State: {state}.")

    def get_rows(self, query_id) -> list[dict]:
        '''
        Parses through the query JSON pages and returns
        a list of dictionaries. Each dictionary is a row of query
        results with the proper column values.
        '''
        # paginator loops through all pages automatically
        pages = self.athena_client.get_paginator("get_query_results").paginate(QueryExecutionId=query_id)
        result = []
        for pg_num, page in enumerate(pages):
            data_rows = page['ResultSet']['Rows']
            column_info = page['ResultSet']['ResultSetMetadata']['ColumnInfo']
            for row_num, row in enumerate(data_rows):
                if row_num == 0 and pg_num == 0:
                    continue
                cells = row['Data']
                data = {
                    col['Name']: self._convert(cell.get("VarCharValue"), col['Type'])
                    for col, cell in zip(column_info, cells, strict=True)
                }
                result.append(data)

        return result

    @staticmethod
    def _convert(value, athena_type):
        '''
        Converts Athena data types to Python data types.
        '''
        if value is None:
            return None
        if athena_type == "varchar":
            return value
        elif athena_type in ["integer", "bigint"]:
            return int(value)
        elif athena_type == "double":
            return float(value)
        elif athena_type == "boolean":
            return value == "true"
        else:
            raise ValueError(f"Unsupported Athena type: {athena_type}")
        
    def fetch_views(self, views) -> dict[str, list[dict]]:
        '''
        Fetches the results for each view in the list of views.
        '''
        query_ids = {view: self.start_query(f"SELECT * FROM {view}") 
                        for view in views}

        result = {}
        for view, query_id in query_ids.items():
            self.wait_for_query(query_id)
            query = self.get_rows(query_id)
            name = view.removeprefix("web_")
            result[name] = query

        return result









