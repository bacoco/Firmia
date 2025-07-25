"""Data export and batch operations MCP tool implementation."""

import asyncio
import csv
import json
import io
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
import base64

from mcp.server.fastmcp import Tool
from pydantic import Field, BaseModel
from structlog import get_logger

from ..cache import get_cache_manager
from ..privacy import apply_privacy_filters, get_audit_logger

logger = get_logger(__name__)


class ExportRequest(BaseModel):
    """Export request parameters."""
    data_type: Literal["search_results", "company_profiles", "analytics_results", "custom_query"]
    format: Literal["json", "csv", "excel"]
    filters: Optional[Dict[str, Any]] = None
    fields: Optional[List[str]] = None
    limit: int = Field(1000, le=10000)
    include_headers: bool = True


class BatchOperationRequest(BaseModel):
    """Batch operation request."""
    operation: Literal["search", "health_score", "profile", "analytics"]
    items: List[Dict[str, Any]]  # List of parameters for each operation
    parallel: bool = Field(True, description="Execute in parallel")
    max_workers: int = Field(5, ge=1, le=20)


class DataExporter:
    """Handles data export in various formats."""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.audit_logger = get_audit_logger()
        self.logger = logger.bind(component="data_exporter")
    
    async def export_search_results(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        format: str,
        limit: int,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Export search results."""
        # Execute search
        from ..tools.search_companies import SearchCompaniesTool
        search_tool = SearchCompaniesTool()
        
        # Prepare search parameters
        search_params = {
            "query": query,
            "page": 1,
            "per_page": min(limit, 25)  # API limit
        }
        if filters:
            search_params.update(filters)
        
        all_results = []
        total_pages = 1
        
        # Paginate through results
        while len(all_results) < limit and search_params["page"] <= total_pages:
            result = await search_tool.run(**search_params)
            
            if result.get("results"):
                all_results.extend(result["results"])
                total_pages = result.get("pagination", {}).get("total_pages", 1)
            
            search_params["page"] += 1
            
            # Respect rate limits
            await asyncio.sleep(0.1)
        
        # Trim to requested limit
        all_results = all_results[:limit]
        
        # Apply privacy filters
        filtered_results = []
        for result in all_results:
            filtered = apply_privacy_filters(result, "export")
            filtered_results.append(filtered)
        
        # Format data
        return self._format_data(filtered_results, format, fields)
    
    async def export_company_profiles(
        self,
        sirens: List[str],
        format: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Export multiple company profiles."""
        from ..tools.get_company_profile import GetCompanyProfileTool
        profile_tool = GetCompanyProfileTool()
        
        profiles = []
        errors = []
        
        # Fetch profiles with rate limiting
        for siren in sirens:
            try:
                result = await profile_tool.run(siren=siren)
                if result.get("company"):
                    # Apply privacy filters
                    filtered = apply_privacy_filters(result["company"], "export")
                    profiles.append(filtered)
            except Exception as e:
                errors.append({"siren": siren, "error": str(e)})
            
            # Rate limit
            await asyncio.sleep(0.2)
        
        # Format data
        formatted = self._format_data(profiles, format, fields)
        formatted["errors"] = errors
        formatted["success_count"] = len(profiles)
        formatted["error_count"] = len(errors)
        
        return formatted
    
    async def export_analytics_results(
        self,
        query_type: str,
        parameters: Dict[str, Any],
        format: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Export analytics query results."""
        # Execute analytics query
        if query_type == "custom":
            # Custom DuckDB query
            query = parameters.get("query")
            params = parameters.get("params", [])
            
            if not query:
                raise ValueError("Query required for custom analytics export")
            
            # Safety check - only allow SELECT queries
            if not query.strip().upper().startswith("SELECT"):
                raise ValueError("Only SELECT queries are allowed")
            
            results = await self.cache_manager.query_analytics(query, params)
        else:
            # Predefined analytics
            from ..analytics import MarketAnalyzer
            analyzer = MarketAnalyzer()
            
            if query_type == "sector_statistics":
                result = await analyzer.get_sector_statistics(
                    naf_code=parameters.get("naf_code"),
                    department=parameters.get("department")
                )
                results = result.data
            elif query_type == "geographic_distribution":
                result = await analyzer.get_geographic_distribution(
                    naf_code=parameters.get("naf_code"),
                    limit=parameters.get("limit", 100)
                )
                results = result.data
            else:
                raise ValueError(f"Unknown analytics query type: {query_type}")
        
        # Format data
        return self._format_data(results, format, fields)
    
    def _format_data(
        self,
        data: List[Dict[str, Any]],
        format: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Format data for export."""
        if not data:
            return {
                "format": format,
                "row_count": 0,
                "content": None,
                "encoding": None
            }
        
        # Filter fields if specified
        if fields:
            filtered_data = []
            for row in data:
                filtered_row = {k: v for k, v in row.items() if k in fields}
                filtered_data.append(filtered_row)
            data = filtered_data
        
        if format == "json":
            content = json.dumps(data, indent=2, default=str)
            return {
                "format": "json",
                "row_count": len(data),
                "content": content,
                "encoding": "utf-8",
                "mime_type": "application/json"
            }
        
        elif format == "csv":
            output = io.StringIO()
            
            if data:
                # Get all unique fields
                all_fields = set()
                for row in data:
                    all_fields.update(row.keys())
                
                fieldnames = sorted(all_fields)
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in data:
                    # Flatten nested objects
                    flat_row = self._flatten_dict(row)
                    writer.writerow(flat_row)
            
            content = output.getvalue()
            return {
                "format": "csv",
                "row_count": len(data),
                "content": content,
                "encoding": "utf-8",
                "mime_type": "text/csv"
            }
        
        elif format == "excel":
            # For Excel, we'll return the data structure
            # Real implementation would use openpyxl or xlsxwriter
            return {
                "format": "excel",
                "row_count": len(data),
                "content": data,  # Would be binary Excel file
                "encoding": "base64",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "note": "Excel export requires additional libraries"
            }
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '') -> Dict[str, Any]:
        """Flatten nested dictionary for CSV export."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key).items())
            elif isinstance(v, list):
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)


class BatchOperationExecutor:
    """Executes batch operations."""
    
    def __init__(self):
        self.logger = logger.bind(component="batch_executor")
    
    async def execute_batch(
        self,
        operation: str,
        items: List[Dict[str, Any]],
        parallel: bool = True,
        max_workers: int = 5
    ) -> Dict[str, Any]:
        """Execute batch operation."""
        results = []
        errors = []
        
        if parallel:
            # Execute in parallel with semaphore
            semaphore = asyncio.Semaphore(max_workers)
            
            async def execute_with_semaphore(item, index):
                async with semaphore:
                    return await self._execute_single(operation, item, index)
            
            tasks = [
                execute_with_semaphore(item, i)
                for i, item in enumerate(items)
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    errors.append({
                        "index": i,
                        "item": items[i],
                        "error": str(result)
                    })
                else:
                    results.append(result)
        else:
            # Execute sequentially
            for i, item in enumerate(items):
                try:
                    result = await self._execute_single(operation, item, i)
                    results.append(result)
                except Exception as e:
                    errors.append({
                        "index": i,
                        "item": item,
                        "error": str(e)
                    })
                
                # Rate limit
                await asyncio.sleep(0.1)
        
        return {
            "operation": operation,
            "total_items": len(items),
            "success_count": len(results),
            "error_count": len(errors),
            "results": results,
            "errors": errors,
            "execution_mode": "parallel" if parallel else "sequential"
        }
    
    async def _execute_single(
        self,
        operation: str,
        parameters: Dict[str, Any],
        index: int
    ) -> Dict[str, Any]:
        """Execute single operation."""
        self.logger.debug("executing_batch_item", operation=operation, index=index)
        
        if operation == "search":
            from ..tools.search_companies import SearchCompaniesTool
            tool = SearchCompaniesTool()
            result = await tool.run(**parameters)
            
        elif operation == "health_score":
            from ..tools.company_analytics import GetCompanyHealthScoreTool
            tool = GetCompanyHealthScoreTool()
            result = await tool.run(**parameters)
            
        elif operation == "profile":
            from ..tools.get_company_profile import GetCompanyProfileTool
            tool = GetCompanyProfileTool()
            result = await tool.run(**parameters)
            
        elif operation == "analytics":
            from ..tools.company_analytics import GetCompanyAnalyticsTool
            tool = GetCompanyAnalyticsTool()
            result = await tool.run(**parameters)
            
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        return {
            "index": index,
            "parameters": parameters,
            "result": result
        }


class ExportDataTool(Tool):
    """MCP tool for exporting data in various formats."""
    
    name = "export_data"
    description = "Export search results, profiles, or analytics data in JSON, CSV, or Excel format"
    
    def __init__(self):
        super().__init__()
        self.exporter = DataExporter()
        self.logger = logger.bind(component="export_data_tool")
    
    async def run(
        self,
        data_type: Literal["search_results", "company_profiles", "analytics_results", "custom_query"] = Field(
            ..., description="Type of data to export"
        ),
        format: Literal["json", "csv", "excel"] = Field(..., description="Export format"),
        query: Optional[str] = Field(None, description="Search query (for search_results)"),
        sirens: Optional[List[str]] = Field(None, description="List of SIRENs (for company_profiles)"),
        analytics_query: Optional[str] = Field(None, description="Analytics query type"),
        parameters: Optional[Dict[str, Any]] = Field(None, description="Additional parameters"),
        filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply"),
        fields: Optional[List[str]] = Field(None, description="Fields to include in export"),
        limit: int = Field(1000, le=10000, description="Maximum rows to export")
    ) -> Dict[str, Any]:
        """Export data."""
        start_time = datetime.utcnow()
        
        try:
            if data_type == "search_results":
                if not query:
                    return {"error": "Query required for search results export"}
                
                result = await self.exporter.export_search_results(
                    query=query,
                    filters=filters,
                    format=format,
                    limit=limit,
                    fields=fields
                )
            
            elif data_type == "company_profiles":
                if not sirens:
                    return {"error": "SIRENs list required for company profiles export"}
                
                result = await self.exporter.export_company_profiles(
                    sirens=sirens[:limit],  # Limit number of profiles
                    format=format,
                    fields=fields
                )
            
            elif data_type == "analytics_results":
                if not analytics_query:
                    return {"error": "Analytics query type required"}
                
                result = await self.exporter.export_analytics_results(
                    query_type=analytics_query,
                    parameters=parameters or {},
                    format=format,
                    fields=fields
                )
            
            elif data_type == "custom_query":
                if not parameters or "query" not in parameters:
                    return {"error": "Custom query required in parameters"}
                
                result = await self.exporter.export_analytics_results(
                    query_type="custom",
                    parameters=parameters,
                    format=format,
                    fields=fields
                )
            
            else:
                return {"error": f"Unknown data type: {data_type}"}
            
            # Add export metadata
            result["export_metadata"] = {
                "data_type": data_type,
                "exported_at": datetime.utcnow().isoformat(),
                "execution_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
            }
            
            # Audit log
            await self.exporter.audit_logger.log_access(
                tool="export_data",
                operation="export",
                caller_id="mcp_client",
                siren=None,
                ip_address=None,
                response_time_ms=result["export_metadata"]["execution_time_ms"],
                status_code=200,
                metadata={
                    "data_type": data_type,
                    "format": format,
                    "row_count": result.get("row_count", 0)
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error("export_failed", error=str(e))
            return {
                "error": str(e),
                "data_type": data_type,
                "format": format
            }


class BatchOperationTool(Tool):
    """MCP tool for batch operations."""
    
    name = "batch_operation"
    description = "Execute batch operations (search, health scores, profiles, analytics)"
    
    def __init__(self):
        super().__init__()
        self.executor = BatchOperationExecutor()
        self.logger = logger.bind(component="batch_operation_tool")
    
    async def run(
        self,
        operation: Literal["search", "health_score", "profile", "analytics"] = Field(
            ..., description="Operation to perform"
        ),
        items: List[Dict[str, Any]] = Field(..., description="List of parameter sets for each operation"),
        parallel: bool = Field(True, description="Execute operations in parallel"),
        max_workers: int = Field(5, ge=1, le=20, description="Maximum parallel workers")
    ) -> Dict[str, Any]:
        """Execute batch operation."""
        if not items:
            return {"error": "No items provided for batch operation"}
        
        if len(items) > 100:
            return {"error": "Maximum 100 items per batch operation"}
        
        self.logger.info("executing_batch_operation",
                        operation=operation,
                        item_count=len(items),
                        parallel=parallel)
        
        result = await self.executor.execute_batch(
            operation=operation,
            items=items,
            parallel=parallel,
            max_workers=max_workers
        )
        
        return result