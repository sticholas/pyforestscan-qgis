"""Representative automatic pilot selection for large-area work plans."""
def select_representative_pilot(work_units,maximum=5):
    units=tuple(work_units)
    if not units:return ()
    indexes={0,len(units)-1,len(units)//2,len(units)//4,(len(units)*3)//4}
    return tuple(units[index] for index in sorted(indexes)[:max(1,maximum)])
def adaptive_core_width(current_width,estimate,minimum=250.0,maximum_replans=2,replan_attempt=0):
    if replan_attempt>=maximum_replans or estimate.recommended_core_width>=current_width:return current_width
    return max(minimum,estimate.recommended_core_width)
