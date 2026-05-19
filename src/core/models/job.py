from typing import Optional, List
from pydantic import BaseModel, Field

class RawJob(BaseModel):
    """Represents a raw job entry from the database."""
    id: int
    url: str
    crawl_run_id: Optional[str] = None
    source_seed_url: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    full_json_dump: str  
    
    # New production fields
    status: str = "pending"
    extraction_method: str = "css"
    raw_markdown: Optional[str] = None
    html_content: Optional[str] = None
    screenshot_path: Optional[str] = None
    retry_count: int = 0

    created_at: Optional[str] = None 
    updated_at: Optional[str] = None
    last_crawled_at: Optional[str] = None


class LLMJobProcess(BaseModel):
    """Structured output expected from the LLM."""
    standardized_title: str = Field(..., description="A standard role title, e.g. AI Engineer, Data Scientist.")
    job_level: Optional[str] = Field(None, description="Job level, e.g., Fresher, Junior, Senior, Manager.")
    is_internship: bool = Field(..., description="True if this is an intern/fresher position.")

    # description: Optional[str] = Field(None, description="Job description text")
    # requirement: Optional[str] = Field(None, description="Job requirements text")  
    # benefit: Optional[str] = Field(None, description="Job benefits text")
    cities: List[str] = Field(..., description="List of cities where the candidate must work, e.g., ['Hanoi', 'Ho Chi Minh'].")

    experience: Optional[float] = Field(None, description="Numeric minimum years required. Use 0 for freshers/interns/no requirement.")
    min_gpa: Optional[float] = Field(None, description="Minimum GPA if mentioned (scale 4.0).")
    english_requirement: Optional[str] = Field(None, description="English requirement, e.g., 'TOEIC 600', 'Fluent'.")

    salary_min: Optional[float] = Field(None,  description="Minimum salary value (in VND or USD). Null if 'Thỏa thuận'.")
    salary_max: Optional[float] = Field(None, description="Maximum salary value. Null if 'Thỏa thuận'.")
    currency: Optional[str] = Field(None, description="Currency (e.g. 'VND', 'USD').")
    is_salary_negotiable: bool = Field(False, description="True if salary is described as 'Thỏa thuận', 'Deal', or 'Negotiable'.")

    tech_stack: List[str] = Field(..., description="List of specific technical skills (Python, PyTorch, AWS, etc.).")
    technical_competencies: List[str] = Field(default_factory=list, description="A list of actions described briefly (e.g. 'Deploy Models', 'Fine-tune LLMs').")
    domain_knowledge: List[str] = Field(..., description="Business domains or concepts (e.g., Computer Vision, NLP, Banking).")

class ProcessedJob(LLMJobProcess):
    """
    Internal job model containing both the LLM-extracted structured data 
    and the text fields extracted via regex.
    """
    company: Optional[str] = Field(None, description="Employer name preserved from raw evidence")
    description: Optional[str] = Field(None, description="Job description text")
    requirement: Optional[str] = Field(None, description="Job requirements text")  
    benefit: Optional[str] = Field(None, description="Job benefits text")
