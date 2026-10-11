import random
from doubt.shift import RoutingPolicy,draw_cases,certify_routing

def test_routed_certificate_is_reproducible_and_explicit():
 rows=draw_cases(500,rng=random.Random(41))
 p=RoutingPolicy('reviews_low_confidence',intensity=.5)
 a=certify_routing(rows,p,grid=20,seed=3)
 assert a==certify_routing(rows,p,grid=20,seed=3)
 assert a['feasible'] is False or a['risk_upper_bound']<=a['alpha']

def test_empty_exposure_is_not_a_success():
 a=certify_routing([],RoutingPolicy('reviews_low_confidence'))
 assert not a['feasible'] and a['n_accepted']==0 and a['risk_upper_bound'] is None

def test_invalid_certificate_inputs_are_rejected():
 import math,pytest
 from doubt.shift import Case
 policy=RoutingPolicy('reviews_low_confidence')
 with pytest.raises(ValueError):certify_routing([],policy,grid=0)
 with pytest.raises(ValueError):certify_routing([Case(math.nan,True)],policy)
