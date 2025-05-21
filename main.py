# -*- coding:utf-8 -*-
try:
    from typing import List, Tuple, Dict, Optional
except ImportError:
    pass

import functools
import Rhino.Geometry as geo  # ignore
import ghpythonlib.components as ghcomp  # ignore
from tqdm import tqdm

import utils

# 모듈 새로고침
import importlib

importlib.reload(utils)

BIGNUM = 100000


class Lot:
    def __init__(self, crv: geo.Curve, record: List[str]):
        self.crv = crv
        self.record = record
        result = geo.AreaMassProperties.Compute(crv)
        self.area = result.Area
        self.centroid = result.Centroid

    def __repr__(self):
        return f"Lot(area={self.area})"

    def __lt__(self, other):
        return self.area < other.area

    def __eq__(self, other):
        return self.area == other.area


def is_similar(base: Lot, other: Lot, tol: float = 0.2):
    """
    두 Curve를 중심점 정렬 후, offset 기반 교차 여부로 유사성 판단
    """

    # 1. 평행이동 벡터 계산 (other을 base 중심으로 정렬)
    move_vector = geo.Vector3d(base.centroid - other.centroid)
    aligned_other = other.crv.DuplicateCurve()
    aligned_other.Translate(move_vector)

    # 2. base offset 수행
    offset_result = utils.Offset().polyline_offset(base.crv, tol, BIGNUM)
    if not offset_result.holes or not offset_result.contour:
        return False

    offset_bases = [offset_result.holes[0], offset_result.contour[0]]

    # 3. 안팎으로 offset 영역과 정렬된 other이 교차하는지 확인
    intersects = any(
        geo.Curve.PlanarCurveCollision(
            offset_base, aligned_other, geo.Plane.WorldXY, 0.01
        )
        for offset_base in offset_bases
    )

    return not intersects  # 교차하지 않으면 유사하다고 판단


def find_all_groups(lots: List[Lot]) -> List[List[Lot]]:
    visited = set()
    groups = []

    for i, base in tqdm(enumerate(lots), total=len(lots), desc="유사 필지 그룹화"):
        if i in visited:
            continue

        group = [base]
        visited.add(i)

        for j, other in enumerate(lots):
            if j == i or j in visited:
                continue
            try:
                if utils.is_similar(base, other):
                    print(f"[find_all_groups] {i}과 {j} 유사 필지 발견")
                    group.append(other)
                    visited.add(j)
            except Exception as e:
                print(f"[find_all_groups 오류] {i}-{j} 비교 중 오류: {e}")

        groups.append(group)

    return groups


def cluster_lots_by_area(
    lots: List[Lot], bin_size: int
) -> Dict[Tuple[int, int], List[Lot]]:

    clusters = {}
    for idx, lot in enumerate(lots):
        bin_idx = int(lot.area // bin_size)
        start = bin_idx * bin_size
        end = start + bin_size
        key = (start, end)
        clusters.setdefault(key, []).append(lots[idx])

    return clusters


# --- 실행 영역 ---
# lot_crvs: Rhino.Geometry.Curve 객체 리스트가 여기에 있어야 함
lots = [Lot(curve, record) for curve, record in zip(lot_crvs, records)]

clusters = cluster_lots_by_area(lots, bin_size=5)

# 상위 10개 클러스터 출력
top_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)[:10]
for i, (key, lot_list) in enumerate(top_clusters, 1):
    print(f"{i}. 구간 {key}: {len(lot_list)}개 필지")

# 가장 큰 클러스터에서 유사 그룹 탐색
target_cluster = top_clusters[0][1]
result = find_all_groups(target_cluster)

# 가장 큰 유사 그룹 출력
largest_group = max(result, key=lambda g: len(g))
print(f"\n가장 큰 유사 그룹: {len(largest_group)}개 필지")
