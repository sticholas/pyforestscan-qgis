"""Single synthesized status model for the compact workspace."""
from dataclasses import dataclass

@dataclass(frozen=True)
class SmartStatusSummary:
    state:str;headline:str;details:tuple[str,...];action:str=''

def build_smart_status(*,backend_ready=False,repository_kind='',polygon_area=None,products=(),output_folder='',processing_state='idle',completed=0,total=0,has_outputs=False,error=''):
    if error:return SmartStatusSummary('needs_attention','Needs attention',(str(error),),'Review details')
    if processing_state in {'running','processing','preparing'}:
        progress=f'{completed} of {total} processing areas complete' if total else 'Processing is underway'
        return SmartStatusSummary('processing','Processing',(progress,),'')
    if has_outputs:return SmartStatusSummary('complete','Complete',('Generated output is ready to load.',),'Load into QGIS')
    missing=[]
    if not backend_ready:missing.append('Managed backend needs attention.')
    if not repository_kind:missing.append('Select LiDAR data.')
    if polygon_area is None:missing.append('Select a processing area.')
    if not products:missing.append('Select a product.')
    if not output_folder:missing.append('Select an output folder.')
    if missing:return SmartStatusSummary('needs_attention',f'{len(missing)} thing{"s" if len(missing)!=1 else ""} need attention',tuple(missing),'')
    area=f'{polygon_area/10000:.3g} ha polygon' if polygon_area is not None else ''
    return SmartStatusSummary('ready','Ready to process',(repository_kind.upper()+' data',area,', '.join(products),'Automatic processing'),'Process LiDAR')
