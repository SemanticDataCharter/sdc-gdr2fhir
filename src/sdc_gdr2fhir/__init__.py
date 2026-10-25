"""sdc-gdr2fhir: Governed Data Records as HL7 FHIR R4 Bundles, through sdc-mapper.

    from sdc_mapper import Engine, load_mapping
    from sdc_gdr2fhir import FHIRMapper, mapping_path
    result = Engine().map_record(xml, FHIRMapper(), load_mapping(mapping_path("xy8upneajsb8vdcmnve01g6g")))

One mapping file per model, in `mappings/`. Registered with sdc-mapper as the target `fhir`.
"""
from pathlib import Path

__version__ = "4.0.2"

MAPPINGS = Path(__file__).with_name("mappings")


def mapping_path(ct_id: str) -> Path:
    """The mapping file this package publishes for a model, by the model's identifier."""
    found = sorted(MAPPINGS.glob(f"*-{ct_id}.yaml"))
    if not found:
        raise FileNotFoundError(f"sdc-gdr2fhir has no mapping for model {ct_id}")
    return found[-1]


from .mapper import FHIRMapper  # noqa: E402

__all__ = ["FHIRMapper", "mapping_path", "MAPPINGS", "__version__"]
