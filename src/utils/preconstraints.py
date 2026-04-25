import itertools
import numpy as np
import torch

class ConstraintBase:
    def __init__(self):
        self.room_unavailable_cache={}      # Key f"{cid1}_{aid1}": True (教室不可用)
        self.constraint_pair_cache={}      # Key f"{cid1}_{aid1}-{cid2}_{aid2}": True (+同教室时间冲突)
        self.constraint_polygon_cache={}   # Key f"{cid1}_{aid1}-{cid2}_{aid2}-{cid3}_{aid3}...": True
        self.nrDays = 7
        self.nrWeeks = 16
        self.travel = {}
        self.classes = []
        self.cid2ind = {}
    
    def sefnrDays(self, nrDays):
        self.nrDays = nrDays

    def sefnrWeeks(self, nrWeeks):
        self.nrWeeks = nrWeeks

    def setTravel(self, travel):
        self.travel = travel

    def setClasses(self, classes):
        self.classes = classes
    
    def setCid2ind(self, cid2ind):
        self.cid2ind = cid2ind

    ##############################################################
    # Tools
    ##############################################################
    def getOptions(self, ind, isCandidate=False):
        if isCandidate:
            rop = self.classes[ind].candidate[0]
            top = self.classes[ind].candidate[1]
            time_option = self.classes[ind].time_options[top]["optional_time_bits"]
            if rop == -1: room_option = None
            else: room_option = self.classes[ind].room_options[rop]
        else:
            if self.classes[ind].action == None:
                return None, None
            rop = self.classes[ind].action[0]
            top = self.classes[ind].action[1]
            time_option = self.classes[ind].time_options[top]["optional_time_bits"]
            if rop == -1: room_option = None
            else: room_option = self.classes[ind].room_options[rop]
        return time_option, room_option

    def merge_slots(self, class_time_slots, S):
        merge_time_slots = []
        merge_time_len = []
        breaks = -1
        class_time_slots = sorted(class_time_slots, key=lambda x: x[0])
        max_slots = 0
        for i, time_slot in enumerate(class_time_slots):
            if breaks == -1:
                merge_time_slots.append(time_slot)
                merge_time_len.append(1)
                breaks += 1
                continue
            start1, end1 = merge_time_slots[breaks]
            start2, end2 = time_slot
            if start1 + end1 + S >= start2:
                merge_time_slots[breaks][1] = max(start2 + end2, start1 + end1) - start1
                merge_time_len[breaks] += 1 
            else:
                merge_time_slots.append(time_slot)
                merge_time_len.append(1)
                breaks += 1
        return breaks, merge_time_slots, merge_time_len

    def _time_overlaps(self, time1, time2):
        """检查两个时间段是否重叠"""
        weeks1, days1, start1, length1 = time1
        weeks2, days2, start2, length2 = time2
        
        # 检查weeks是否有交集
        weeks_int1 = int(weeks1, 2)
        weeks_int2 = int(weeks2, 2)
        if (weeks_int1 & weeks_int2) == 0:
            return False
        
        # 检查days是否有交集
        days_int1 = int(days1, 2)
        days_int2 = int(days2, 2)
        if (days_int1 & days_int2) == 0:
            return False
        
        # 检查时间段是否重叠
        end1 = start1 + length1
        end2 = start2 + length2
        
        return (start1 < end2) and (start2 < end1)
    
# ================================================================
#                      Hard Constraints
# ================================================================
class HardConstraints(ConstraintBase):
    """违反即失败：返回 True=违反，False=满足"""

    def _violation_rate(self, cons, cid1=None, aid1=None, room1=None, time1=None, cid2=None, aid2=None, room2=None, time2=None):
        if self.room_unavailable_cache.get(f"{cid2}_{aid2}", False):
            return True
        ctype = cons["type"]
        if "(" in ctype and ")" in ctype:
            base, attr = ctype.split("(")[0], ctype.split("(")[1].split(")")[0]
            return getattr(self, base)(cons, attr, cid1, aid1, room1, time1, cid2, aid2, room2, time2)
        else:
            return getattr(self, ctype)(cons, cid1, aid1, room1, time1, cid2, aid2, room2, time2)
    
    def _time_conflicts_with_unavailable(self, time_bits, unavail_bits):
        """
        检查课程时间是否与教室不可用时间冲突
        
        Args:
            time_bits: (weeks_bits, days_bits, start, length) - 课程时间
            unavail_bits: (weeks_bits, days_bits, start, length) - 不可用时间
        
        Returns:
            bool: True if 有冲突
        """
        class_weeks, class_days, class_start, class_length = time_bits
        unavail_weeks, unavail_days, unavail_start, unavail_length = unavail_bits
        
        # 检查weeks是否有交集
        weeks_int1 = int(class_weeks, 2)
        weeks_int2 = int(unavail_weeks, 2)
        if (weeks_int1 & weeks_int2) == 0:
            return False
        
        # 检查days是否有交集
        days_int1 = int(class_days, 2)
        days_int2 = int(unavail_days, 2)
        if (days_int1 & days_int2) == 0:
            return False
        
        # 检查时间段是否重叠
        class_end = class_start + class_length
        unavail_end = unavail_start + unavail_length
        
        if not ((class_start < unavail_end) and (unavail_start < class_end)):
            return False
        
        return True

    def RoomTimeConflict(self, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        if room1 and room2 and room1['id'] == room2['id']:
            if self._time_overlaps(time1, time2):
                key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
                self.constraint_pair_cache[key1] = True
                key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
                self.constraint_pair_cache[key2] = True
                return True
    
    # ---- Pair-wise 类型 ----

    def SameRoom(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        if room1 and room2 and room1['id'] != room2['id']:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        return False

    def DifferentRoom(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        if room1 and room2 and room1['id'] == room2['id']:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        return False

    def SameStart(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        _, _, start1, _ = time1
        _, _, start2, _ = time2
        if start1 != start2:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        return False

    def SameTime(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        _, _, start1, end1 = time1
        _, _, start2, end2 = time2
        if start1 <= start2 and start2 + end2 <= start1 + end1:
            return False
        elif start2 <= start1 and start1 + end1 <= start2 + end2:
            return False
        else:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        
    def DifferentTime(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        _, _, start1, end1 = time1
        _, _, start2, end2 = time2
        if (start1 + end1 <= start2) or (start2 + end2 <= start1):
            return False
        else:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True

    def SameDays(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        _, day_bits1, _, _ = time1
        days_int1 = int(day_bits1, 2)
        _, day_bits2, _, _ = time2
        days_int2 = int(day_bits2, 2)
        or_ = days_int1 | days_int2
        if not (or_ == days_int1 or or_ == day_bits2):
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        return False

    def DifferentDays(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        _, day_bits1, _, _ = time1
        days_int1 = int(day_bits1, 2)
        _, day_bits2, _, _ = time2
        days_int2 = int(day_bits2, 2)
        and_ = days_int1 & days_int2
        if not and_ == 0:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        return False

    def SameWeeks(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        week_bits1, _, _, _ = time1
        week_int1 = int(week_bits1, 2)
        week_bits2, _, _, _ = time2
        week_int2 = int(week_bits2, 2)
        or_ = week_int1 | week_int2
        if not (or_ == week_int1 or or_ == week_int2):
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        return False

    def DifferentWeeks(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        week_bits1, _, _, _ = time1
        week_int1 = int(week_bits1, 2)
        week_bits2, _, _, _ = time2
        week_int2 = int(week_bits2, 2)
        and_ = week_int1 & week_int2
        if not and_ == 0:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        return False

    def Overlap(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        week_bits1, day_bits1, start1, end1 = time1
        week_bits2, day_bits2, start2, end2 = time2
        days_int1 = int(day_bits1, 2)
        days_int2 = int(day_bits2, 2)
        and_days = days_int1 & days_int2
        week_int1 = int(week_bits1, 2)
        week_int2 = int(week_bits2, 2)
        and_week = week_int1 & week_int2
        if (start1 < start2 + end2) and (start2 < start1 + end1) and (not and_days == 0) and (not and_week == 0):
            return False
        else:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True

    def NotOverlap(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        week_bits1, day_bits1, start1, end1 = time1
        week_bits2, day_bits2, start2, end2 = time2
        days_int1 = int(day_bits1, 2)
        days_int2 = int(day_bits2, 2)
        and_days = days_int1 & days_int2
        week_int1 = int(week_bits1, 2)
        week_int2 = int(week_bits2, 2)
        and_week = week_int1 & week_int2
        if (start1 + end1 <= start2) or (start2 + end2 <= start1) or (and_days == 0) or (and_week == 0):
            return False
        else:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True

    def SameAttendees(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        # (Ci.end + travel(Ci.room→Cj.room) ≤ Cj.start) ∨ (Cj.end + travel(Cj.room→Ci.room) ≤ Ci.start)
        # 或 天/周不重叠即满足
        if room1:
            room_id1 = room1['id']
        else:
            room_id1 = -1
        week_bits1, day_bits1, start1, end1 = time1
        if room2:
            room_id2 = room2['id']
        else:
            room_id2 = -1
        travel1 = self.travel.get(room_id1, {}).get(room_id2, 0)
        travel2 = self.travel.get(room_id2, {}).get(room_id1, 0)
        week_bits2, day_bits2, start2, end2 = time2
        days_int1 = int(day_bits1, 2)
        days_int2 = int(day_bits2, 2)
        and_days = days_int1 & days_int2
        week_int1 = int(week_bits1, 2)
        week_int2 = int(week_bits2, 2)
        and_week = week_int1 & week_int2
        if (start1 < start2 + end2) and (start2 < start1 + end1) and (not and_days == 0) and (not and_week == 0): # Overlap
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
        if (start1 + end1 + travel1 <= start2) or (start2 + end2 + travel2 <= start1) or (and_days == 0) or (and_week == 0):
            return False
        else:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True

    def Precedence(self, hc, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        # 列表顺序：C1 在 C2 之前... 按“first(week)->first(day)->end<=start”
        cids = hc["classes"]
        i = cids.index(cid1)
        j = cids.index(cid2)
        week_bits1, day_bits1, start1, end1 = time1
        week_bits2, day_bits2, start2, end2 = time2
        first_day1 = day_bits1.find('1')
        first_day2 = day_bits2.find('1')
        first_week1 = week_bits1.find('1')
        first_week2 = week_bits2.find('1')
        if i < j:
            w_pre, d_pre, s_pre, e_pre = first_week1, first_day1, start1, end1
            w_sub, d_sub, s_sub, e_sub = first_week2, first_day2, start2, end2
        else:
            w_pre, d_pre, s_pre, e_pre = first_week2, first_day2, start2, end2
            w_sub, d_sub, s_sub, e_sub = first_week1, first_day1, start1, end1
        if (w_pre < w_sub) or ( # first(week_i) < first(week_j) or
            (w_pre == w_sub) and (
                (d_pre < d_sub ) or ( # first(day_i) < first(day_j) or
                    (d_pre == d_sub) and (s_pre+e_pre <= s_sub) # end_i <= start_j
                )
            )
        ):
            return False
        else:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True

    def WorkDay(self, hc, S, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        # 同天同周：max(end)-min(start) ≤ S
        S = int(S)
        week_bits1, day_bits1, start1, end1 = time1
        week_bits2, day_bits2, start2, end2 = time2
        days_int1 = int(day_bits1, 2)
        days_int2 = int(day_bits2, 2)
        and_days = days_int1 & days_int2
        week_int1 = int(week_bits1, 2)
        week_int2 = int(week_bits2, 2)
        and_week = week_int1 & week_int2
        if (and_days == 0) or (and_week == 0) or ((max(start1 + end1, start2 + end2) - min(start1, start2)) <= S):
            return False
        else:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True

    def MinGap(self, hc, G, cid1, aid1, room1, time1, cid2, aid2, room2, time2):
        # 同天同周：要求 end+G ≤ start（任意顺序其中之一）
        G = int(G)
        week_bits1, day_bits1, start1, end1 = time1
        week_bits2, day_bits2, start2, end2 = time2
        days_int1 = int(day_bits1, 2)
        days_int2 = int(day_bits2, 2)
        and_days = days_int1 & days_int2
        week_int1 = int(week_bits1, 2)
        week_int2 = int(week_bits2, 2)
        and_week = week_int1 & week_int2
        if (and_days == 0) or (and_week == 0) or (start1 + end1 + G <= start2) or (start2 + end2 + G <= start1):
            return False
        else:
            key1 = f"{cid1}_{aid1}-{cid2}_{aid2}"
            self.constraint_pair_cache[key1] = True
            key2 = f"{cid2}_{aid2}-{cid1}_{aid1}"
            self.constraint_pair_cache[key2] = True
            return True
    
    # ---- Pair-wise 类型 ----
# ================================================================
#                      Soft Constraints
# ================================================================
class SoftConstraints(ConstraintBase):
    """
    返回违反率 (0~1) 或违反次数；外层乘 penalty。
    """
    def _violation_rate(self, cons, cid=None):
        ctype = cons["type"]
        if "(" in ctype and ")" in ctype:
            base, attr = ctype.split("(")[0], ctype.split("(")[1].split(")")[0]
            if base not in self.masks:
                return 0
            if cid:
                return getattr(self, base)(cons, attr, cid)
            return getattr(self, base)(cons, attr)
        if ctype not in self.masks:
            return 0
        if cid:
            return getattr(self, ctype)(cons, cid)
        return getattr(self, ctype)(cons)