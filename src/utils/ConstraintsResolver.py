import torch
from tqdm import tqdm
from itertools import combinations, product

class ConstraintsResolver:
    def __init__(self, reader, device='cuda', polygon=False):
        self.reader = reader
        self.device = device
        self.polygon = polygon
        self.u = {}  # u[cid]: 课程-未分配 -> index of u_tensor 
        self.x = {}  # x[cid, time_idx, room_id]: 课程-时间-教室 -> index of x_tensor 
        self.y = {}  # x[cid, time_idx]: 课程-时间 -> index list of x_tensor 
        self.w = {}  # x[cid, room_id]: 课程-教室 -> index list of x_tensor 

        self.valid_solution_constraint = {} # key: (index list of x_tensor | None, index list of u_tensor, lower boundary, upper boundary)
        self.hard_constraints = {} # key: (index list of x_tensor, upper boundary)
        self.soft_constraints = {} # key: (index list of x_tensor, upper boundary, penalty)

        # 索引映射
        self.class_to_time_options = {}  # {cid: [(time_option, time_idx), ...]}
        self.class_to_room_options = {}  # {cid: [room_id, ...]}
        self.class_to_valid_options = {} # [cid, time_idx, room_id]: True

        self.hard_constraints_cache = {}
        self.time_conflict_cache = {}

        self.build_model()

    def build_model(self):
        """构建完整的张量约束模型"""
        print("\n=== Building tensor constraint model ===")
        
        # 1. 预处理：建立索引
        self._build_indices()

        # 2. 创建变量
        self._create_variables()
        
        # 3. 添加基础约束
        self._add_primary_constraints()

        # 4. 添加分布约束
        self._add_distribution_constraints()

        # 5. 设置目标函数
        self._set_objective()

    def _build_indices(self):
        """构建课程到时间/教室选项的索引"""
        print("Building indices...")
        
        for cid, class_data in self.reader.classes.items():
            # 时间选项
            time_options = []
            for idx, topt in enumerate(class_data['time_options']):
                time_options.append((topt, idx))
            self.class_to_time_options[cid] = time_options
            
            # 教室选项
            room_options = []
            for ropt in class_data['room_options']:
                room_options.append(ropt['id'])
            
            # 如果不需要教室，添加虚拟教室
            if not class_data['room_required']:
                room_options = ['dummy']
            self.class_to_room_options[cid] = room_options

            options = []
            for topt, tidx in time_options:
                for rid in room_options:
                    self.class_to_valid_options[cid, tidx, rid] = True
            
        print(f"Indexed {len(self.class_to_time_options)} classes")

    def _create_variables(self):
        """创建决策变量"""
        print("Creating variables...")
        
        class_count = 0
        var_count = 0
        filtered_count = 0
        
        for cid in self.reader.classes.keys():
            time_options = self.class_to_time_options[cid]
            room_options = self.class_to_room_options[cid]
            self.u[cid] = class_count
            class_count += 1

            # 创建 x[cid, time_idx, room_id]
            for topt, tidx in time_options:
                time_mat = topt['optional_time']
                for rid in room_options:
                    # 检查这个时间-教室组合是否可用
                    if rid != 'dummy' and not self._is_room_available(rid, time_mat=time_mat):
                        # 跳过不可用的组合
                        self.class_to_valid_options[cid, tidx, rid] = False
                        filtered_count += 1
                        continue

                    self.x[cid, tidx, rid] = var_count
                    if self.y.get((cid, tidx), None) == None: self.y[cid, tidx] = []
                    self.y[cid, tidx].append(var_count)
                    if self.w.get((cid, tidx), None) == None: self.w[cid, rid] = []
                    self.w[cid, rid].append(var_count)
                    var_count += 1

        print(f"Filtered {filtered_count} varibles")
        
        self.u_tensor = torch.zeros(class_count, device=self.device)
        self.x_tensor = torch.zeros(var_count, device=self.device)
        print(f"u_tensor shape: {self.u_tensor.shape}; x_tensor shape: {self.x_tensor.shape}")
        print(f"Created {class_count + var_count} varibles")

    def _add_primary_constraints(self):
        """创建基本限制"""
        print("Creating primary constraints...")
        # 1. 每个课程必须分配恰好一个时间和教室
        for cid in self.reader.classes.keys():
            time_options = self.class_to_time_options[cid]
            room_options = self.class_to_room_options[cid]
            # 收集所有有效的x变量
            valid_x_vars = []
            for _, tidx in time_options:
                for rid in room_options:
                    if (cid, tidx, rid) in self.x:
                        valid_x_vars.append(self.x[cid, tidx, rid])
            if valid_x_vars:
                self.valid_solution_constraint[f"assign_{cid}"] = (valid_x_vars, self.u[cid], 1, 1)
            else:
                self.valid_solution_constraint[f"assign_unavail_{cid}"] = (None, self.u[cid], 1, 1)
                self.logger.info(f"Warning: Class {cid} has no valid time-room combinations!")
        print(f"Created {len(self.valid_solution_constraint)} primary constraints...")

    def _add_distribution_constraints(self):
        """添加分布约束"""
        print("Adding distribution constraints...")
        self.hard_dist_tensor = None
        self.soft_dist_tensor = None

        # 硬约束
        for constraint in tqdm(self.reader.distributions['hard_constraints'], total=len(self.reader.distributions['hard_constraints'])):
            self._add_single_distribution_constraint(constraint, is_hard=True)
        
        self._add_room_capacity_constraints()
        self.hard_dist_tensor, hc_upper = self.build_hard_dist()
        self.hard_dist_upper_tensor = hc_upper.view(1, -1)

        print(f"Distribution constraints added, {len(self.hard_constraints)} hard constraints")

        # 软约束
        for constraint in tqdm(self.reader.distributions['soft_constraints'], total=len(self.reader.distributions['soft_constraints'])):
            self._add_single_distribution_constraint(constraint, is_hard=False)

        self.soft_dist_tensor, sc_upper, sc_cost = self.build_soft_dist()
        self.soft_dist_upper_tensor = sc_upper.view(1, -1)
        self.soft_dist_cost_tensor  = sc_cost.view(1, -1)

        print(f"Distribution constraints added, {len(self.soft_constraints)} soft constraints")

    def _add_single_distribution_constraint(self, constraint, is_hard):
        """添加单个分布约束"""
        ctype = constraint['type']
        classes = constraint['classes']
        penalty = constraint.get('penalty', 0)
        disploygon = not self.polygon
        # 根据约束类型调用相应的处理函数
        if ctype == 'SameStart':
            self._add_same_start_constraint(classes, is_hard, penalty)
        elif ctype == 'SameTime':
            self._add_same_time_constraint(classes, is_hard, penalty)
        elif ctype == 'DifferentTime':
            self._add_different_time_constraint(classes, is_hard, penalty)
        elif ctype == 'SameDays':
            self._add_same_days_constraint(classes, is_hard, penalty)
        elif ctype == 'DifferentDays':
            self._add_different_days_constraint(classes, is_hard, penalty)
        elif ctype == 'SameWeeks':
            self._add_same_weeks_constraint(classes, is_hard, penalty)
        elif ctype == 'DifferentWeeks':
            self._add_different_weeks_constraint(classes, is_hard, penalty)
        elif ctype == 'SameRoom':
            self._add_same_room_constraint(classes, is_hard, penalty)
        elif ctype == 'DifferentRoom':
            self._add_different_room_constraint(classes, is_hard, penalty)
        elif ctype == 'Overlap':
            self._add_overlap_constraint(classes, is_hard, penalty)
        elif ctype == 'NotOverlap':
            self._add_not_overlap_constraint(classes, is_hard, penalty)
        elif ctype == 'SameAttendees':
            self._add_same_attendees_constraint(classes, is_hard, penalty)
        elif ctype == 'Precedence':
            self._add_precedence_constraint(classes, is_hard, penalty)
        elif ctype.startswith('WorkDay'):
            max_slots = int(ctype.split('(')[1].rstrip(')'))
            self._add_workday_constraint(classes, max_slots, is_hard, penalty)
        elif ctype.startswith('MinGap'):
            min_gap = int(ctype.split('(')[1].rstrip(')'))
            self._add_min_gap_constraint(classes, min_gap, is_hard, penalty)
        ##############################################################################################
        # Polygon constraints
        ##############################################################################################
        elif ctype.startswith('MaxDays'):
            # After X_tensor has been assigned
            max_days = int(ctype.split('(')[1].rstrip(')'))
            self._add_max_days_constraint(classes, max_days, is_hard, penalty, disploygon)
        elif ctype.startswith('MaxDayLoad'):
            # After X_tensor has been assigned
            max_slots = int(ctype.split('(')[1].rstrip(')'))
            self._add_max_day_load_constraint(classes, max_slots, is_hard, penalty, disploygon)
        elif ctype.startswith('MaxBreaks'):
            # After X_tensor has been assigned
            # 解析 MaxBreaks(R,S) 格式
            params = ctype.split('(')[1].rstrip(')').split(',')
            max_breaks = int(params[0])
            min_break_length = int(params[1])
            self._add_max_breaks_constraint(classes, max_breaks, min_break_length, is_hard, penalty, disploygon)
        elif ctype.startswith('MaxBlock'):
            # After X_tensor has been assigned
            # 解析 MaxBlock(M,S) 格式
            params = ctype.split('(')[1].rstrip(')').split(',')
            max_block_length = int(params[0])
            max_gap_in_block = int(params[1])
            self._add_max_block_constraint(classes, max_block_length, max_gap_in_block, is_hard, penalty, disploygon)
        else:
            print(f"Warning: Constraint type '{ctype}' not implemented")
    
    def _set_objective(self):
        """设置目标函数"""
        print("Setting objective...")
        
        # Priority 1: Minimize unassigned
        # 目标1：torch.matmul(u.view(1, -1), w_u.view(-1, 1)) == 0

        w_u = torch.ones_like(self.u_tensor, device=self.x_tensor.device)
        self.objective_u = (w_u, 0) # (w_u, target)

        print("\nObjective 1: Minimize unassigned")
        print("torch.matmul(u.view(1, -1), w_u.view(-1, 1)) == 0")

        # Priority 2: Minimize Hard Constraints
        # 目标2：
        # hard constraints: torch.sum((torch.matmul(x.view(1, -1), hard_dist.T) - hard_upper_dist).clamp(min=0.0)) == 0
        
        hard_dist = self.hard_dist_tensor # shape (hard_dist length, x length)
        hard_upper_dist = self.hard_dist_upper_tensor # shape (1, hard_dist length)

        self.objective_hc = (hard_dist, hard_upper_dist, 0)

        print("\nObjective 2: Minimize Hard Constraints")
        print("hard constraints: torch.sum((torch.matmul(x.view(1, -1), hard_dist.T) - hard_upper_dist).clamp(min=0.0)) == 0")

        # Priority 3: Minimize penalty
        # 目标3：
        # time penalty = torch.matmul(x.view(1, -1), w_time.view(-1, 1))
        # room penalty = torch.matmul(x.view(1, -1), w_room.view(-1, 1))
        # soft penalty = torch.sum(torch.mul((torch.matmul(x.view(1, -1), soft_dist.T) - upper_dist).clamp(min=0.0), w_dist))
        # total penalty = time penalty + room penalty + soft penalty

        # 1. 时间惩罚
        opt_weights = self.reader.optimization
        time_weight = opt_weights.get('time', 0) if opt_weights else 0
        w_time = torch.zeros_like(self.x_tensor, device=self.x_tensor.device)
        for cid in self.reader.classes.keys():
            time_opts = self.class_to_time_options[cid]
            for topt, tidx in time_opts:
                penalty = topt.get('penalty', 0)
                if penalty > 0:
                    if self.y.get((cid, tidx), None):
                        w_time[self.y[cid, tidx]] += time_weight * penalty

        # 2. 教室惩罚
        room_weight = opt_weights.get('room', 0) if opt_weights else 0
        w_room = torch.zeros_like(self.x_tensor, device=self.x_tensor.device)
        for cid in self.reader.classes.keys():
            class_data = self.reader.classes[cid]
            for ropt in class_data['room_options']:
                rid = ropt['id']
                penalty = ropt.get('penalty', 0)
                if penalty > 0 and (cid, rid) in self.w:
                    if self.w.get((cid, rid), None):
                        w_room[self.w[cid, rid]] += room_weight * penalty
        
        # 3. 分布约束惩罚
        dist_weight = opt_weights.get('distribution', 0) if opt_weights else 0

        soft_dist = self.soft_dist_tensor # shape (soft_dist length, x length)
        soft_upper_dist = self.soft_dist_upper_tensor # shape (1, soft_dist length)
        w_dist = dist_weight * self.soft_dist_cost_tensor # shape (1, soft_dist length)

        self.objective_penalty = (w_time, w_room, (soft_dist, soft_upper_dist, w_dist), 0)

        print("\nObjective 2: Minimize penalty")
        print("time penalty = torch.matmul(x.view(1, -1), w_time.view(-1, 1))")
        print("room penalty = torch.matmul(x.view(1, -1), w_room.view(-1, 1))")
        print("soft penalty = torch.sum(torch.mul((torch.matmul(x.view(1, -1), soft_dist.T) - upper_dist).clamp(min=0.0), w_dist))")
        print("total penalty = time penalty + room penalty + soft penalty -> 0")

        return self.objective_u, self.objective_penalty

    #######################################################################################################
    # Constraints: (Pair-wise) Time
    #######################################################################################################

    def _add_same_start_constraint(self, classes, is_hard, penalty):
        """
        SameStart: 课程必须在相同的开始时间
        即：start time必须相同
        """
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    if topt1['optional_time_bits'][2] != topt2['optional_time_bits'][2]:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"SameStart_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"SameStart_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    def _add_same_time_constraint(self, classes, is_hard, penalty):
        """SameTime: 所有课程必须在相同时间"""
        if len(classes) < 2:
            return
        
        # 对每对课程
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            # 找到时间完全相同的选项对
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    _, _, start1, end1 = topt1["optional_time_bits"]
                    _, _, start2, end2 = topt2["optional_time_bits"]
                    if start1 <= start2 and start2 + end2 <= start1 + end1:
                        continue
                    elif start2 <= start1 and start1 + end1 <= start2 + end2:
                        continue
                    else:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"SameTime_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"SameTime_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)
    
    def _add_different_time_constraint(self, classes, is_hard, penalty):
        """DifferentTime: 课程必须在不同时间"""
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            # 找到时间相同的选项对，禁止同时选择
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    _, _, start1, end1 = topt1['optional_time_bits']
                    _, _, start2, end2 = topt2['optional_time_bits']
                    if (start1 + end1 <= start2) or (start2 + end2 <= start1):
                        continue
                    else:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"DifferentTime_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"DifferentTime_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    def _add_same_days_constraint(self, classes, is_hard, penalty):
        """
        SameDays: 课程必须在相同的星期几
        即：days_bits必须完全相同
        """
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    day_bits1 = topt1['optional_time_bits'][1]
                    days_int1 = int(day_bits1, 2)
                    day_bits2 = topt2['optional_time_bits'][1]
                    days_int2 = int(day_bits2, 2)
                    or_ = days_int1 | days_int2
                    if not (or_ == days_int1 or or_ == day_bits2):
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"SameDays_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"SameDays_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    def _add_different_days_constraint(self, classes, is_hard, penalty):
        """
        DifferentDays: 课程必须在不同的星期几
        即：days_bits不能有交集
        """
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    day_bits1 = topt1['optional_time_bits'][1]
                    days_int1 = int(day_bits1, 2)
                    day_bits2 = topt2['optional_time_bits'][1]
                    days_int2 = int(day_bits2, 2)
                    and_ = days_int1 & days_int2
                    if not and_ == 0:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"DifferentDays_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"DifferentDays_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    def _add_same_weeks_constraint(self, classes, is_hard, penalty):
        """
        SameWeeks: 课程必须在相同的周
        即：weeks_bits必须完全相同
        """
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    week_bits1 = topt1['optional_time_bits'][0]
                    week_int1 = int(week_bits1, 2)
                    week_bits2 = topt2['optional_time_bits'][0]
                    week_int2 = int(week_bits2, 2)
                    or_ = week_int1 | week_int2
                    if not (or_ == week_int1 or or_ == week_int2):
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"SameWeeks_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"SameWeeks_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    def _add_different_weeks_constraint(self, classes, is_hard, penalty):
        """
        DifferentWeeks: 课程必须在不同的周
        即：weeks_bits不能有交集
        """
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    week_bits1 = topt1['optional_time_bits'][0]
                    week_int1 = int(week_bits1, 2)
                    week_bits2 = topt2['optional_time_bits'][0]
                    week_int2 = int(week_bits2, 2)
                    and_ = week_int1 & week_int2
                    if not and_ == 0:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"DifferentWeeks_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"DifferentWeeks_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    def _add_overlap_constraint(self, classes, is_hard, penalty):
        """
        Overlap: 课程必须重叠
        即：至少有一对课程的时间必须有重叠
        
        这个约束的逻辑是：
        - 如果选择了classes中的任意两个课程，它们的时间必须重叠
        - 实现方式：对每对课程，如果它们的时间不重叠，则不能同时选择
        """
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    week_bits1, day_bits1, start1, end1 = topt1['optional_time_bits']
                    week_bits2, day_bits2, start2, end2 = topt2['optional_time_bits']
                    days_int1 = int(day_bits1, 2)
                    days_int2 = int(day_bits2, 2)
                    and_days = days_int1 & days_int2
                    week_int1 = int(week_bits1, 2)
                    week_int2 = int(week_bits2, 2)
                    and_week = week_int1 & week_int2
                    if (start1 < start2 + end2) and (start2 < start1 + end1) and (not and_days == 0) and (not and_week == 0):
                        continue
                    else:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"Overlap_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"Overlap_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)
    
    def _add_not_overlap_constraint(self, classes, is_hard, penalty):
        """NotOverlap: 课程时间不能重叠"""
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    week_bits1, day_bits1, start1, end1 = topt1['optional_time_bits']
                    week_bits2, day_bits2, start2, end2 = topt2['optional_time_bits']
                    days_int1 = int(day_bits1, 2)
                    days_int2 = int(day_bits2, 2)
                    and_days = days_int1 & days_int2
                    week_int1 = int(week_bits1, 2)
                    week_int2 = int(week_bits2, 2)
                    and_week = week_int1 & week_int2
                    if (start1 + end1 <= start2) or (start2 + end2 <= start1) or (and_days == 0) or (and_week == 0):
                        continue
                    else:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"NotOverlap_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"NotOverlap_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    def _add_same_attendees_constraint(self, classes, is_hard, penalty):
        """
        SameAttendees: 参与者可以参加所有课程
        即：课程时间不能重叠，且考虑教室间的旅行时间
        
        这个约束分为两部分：
        1. 时间重叠检查（已被NotOverlap覆盖）
        2. 时间-教室重叠检查（考虑旅行时间）
        """
        if len(classes) < 2:
            return
        
        # 获取travel时间矩阵（如果存在）
        travel_times = self.reader.travel if self.reader.travel else {}
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            room_opts1 = self.class_to_room_options[c1]
            room_opts2 = self.class_to_room_options[c2]

            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                week_bits1, day_bits1, start1, end1 = topt1['optional_time_bits']
                
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    week_bits2, day_bits2, start2, end2 = topt2['optional_time_bits']

                    days_int1 = int(day_bits1, 2)
                    days_int2 = int(day_bits2, 2)
                    and_days = days_int1 & days_int2
                    week_int1 = int(week_bits1, 2)
                    week_int2 = int(week_bits2, 2)
                    and_week = week_int1 & week_int2

                    # Overlap
                    if (start1 < start2 + end2) and (start2 < start1 + end1) and (not and_days == 0) and (not and_week == 0):
                        x_index = []
                        x_index.extend(self.y[c1, tidx1])
                        x_index.extend(self.y[c2, tidx2])
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"SameAttendees_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"SameAttendees_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

                    # 检查时间-教室冲突（考虑旅行时间）
                    else:
                        # 如果两个课程在同一天但时间紧邻，需要检查教室距离
                        for r1 in room_opts1:
                            for r2 in room_opts2:
                                if r1 == 'dummy' or r2 == 'dummy':
                                    continue
                                
                                # 获取旅行时间
                                travel1 = travel_times.get(r1, {}).get(r2, 0)
                                travel2 = travel_times.get(r2, {}).get(r1, 0)
                                
                                # 检查是否有足够的时间旅行
                                if (start1 + end1 + travel1 <= start2) or (start2 + end2 + travel2 <= start1) or (and_days == 0) or (and_week == 0):
                                    continue
                                else:
                                    x_index = []
                                    x_index.append(self.x[c1, tidx1, r1])
                                    x_index.append(self.x[c2, tidx2, r2])
                                    if is_hard:
                                        if (c1, tidx1, r1) in self.x and (c2, tidx2, r2) in self.x:
                                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                                            self.hard_constraints[f"SameAttendees_{c1}_{tidx1}_{r1}_{c2}_{tidx2}_{r2}"] = (x_index, 1)
                                    else:
                                        if (c1, tidx1, r1) in self.x and (c2, tidx2, r2) in self.x:
                                            self.soft_constraints[f"SameAttendees_{c1}_{tidx1}_{r1}_{c2}_{tidx2}_{r2}"] = (x_index, 1, penalty)

    def _add_precedence_constraint(self, classes, is_hard, penalty):
        """Precedence: 课程必须按顺序进行"""
        if len(classes) < 2:
            return
        
        # 假设classes列表的顺序就是优先级顺序
        for i in range(len(classes) - 1):
            c1 = classes[i]
            c2 = classes[i + 1]
            
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            # c1必须在c2之前结束
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    week_bits1, day_bits1, start1, end1 = topt1['optional_time_bits']
                    week_bits2, day_bits2, start2, end2 = topt2['optional_time_bits']
                    first_day1 = day_bits1.find('1')
                    first_day2 = day_bits2.find('1')
                    first_week1 = week_bits1.find('1')
                    first_week2 = week_bits2.find('1')
                    w_pre, d_pre, s_pre, e_pre = first_week1, first_day1, start1, end1
                    w_sub, d_sub, s_sub, e_sub = first_week2, first_day2, start2, end2
                    if (w_pre < w_sub) or ( # first(week_i) < first(week_j) or
                        (w_pre == w_sub) and (
                            (d_pre < d_sub ) or ( # first(day_i) < first(day_j) or
                                (d_pre == d_sub) and (s_pre+e_pre <= s_sub) # end_i <= start_j
                            )
                        )
                    ):
                        continue
                    else:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"Precedence_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"Precedence_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    def _add_workday_constraint(self, classes, max_slots, is_hard, penalty):
        """
        Workday(S): 限制每天的工作时长
        
        使用枚举所有可能的时间跨度组合的方法
        这种方法更直接，但可能产生较多约束
        """
        if len(classes) == 0:
            return
        events_start_slot = [{} for _ in range(self.reader.slotsPerDay)]
        events_end_slot = [{} for _ in range(self.reader.slotsPerDay)]
        for cid in classes:
            if cid not in self.reader.classes:
                continue
            time_opts = self.class_to_time_options[cid]
            for topt, tidx in time_opts:
                if self.y.get((cid, tidx), None) == None:
                    continue
                bits = topt['optional_time_bits']
                weeks_bits, days_bits, start, length = bits
                end = start + length
                if length > max_slots:
                    x_index = self.y[cid, tidx]
                    if is_hard:
                        if self.hard_constraints_cache.get(f"y_{cid}_{tidx}_0", False) == True: continue
                        else: self.hard_constraints_cache[f"y_{cid}_{tidx}_0"] = True
                        self.hard_constraints[f"WorkDay_{cid}_{tidx}"] = (x_index, 0)
                    else:
                        self.soft_constraints[f"WorkDay_{cid}_{tidx}"] = (x_index, 0, penalty)
                    continue
                if events_start_slot[start].get(cid, None) == None:
                    events_start_slot[start][cid] = []
                else:
                    events_start_slot[start][cid].append((cid, tidx, start, end, bits))
                if events_start_slot[end].get(cid, None) == None:
                    events_end_slot[end][cid] = []
                else:
                    events_end_slot[end][cid].append((cid, tidx, start, end, bits))

        for start in range(self.reader.slotsPerDay - max_slots):
            for c1 in classes:
                if c1 not in events_start_slot[start]:
                    continue
                for (_, t1, start1, end1, time_bits1) in events_start_slot[start][c1]:
                    for end in range(start1 + max_slots, self.reader.slotsPerDay):
                        for c2 in classes:
                            if c2 == c1:
                                continue
                            if c2 not in events_start_slot[end]:
                                continue
                            for (_, t2, start2, end2, time_bits2) in events_start_slot[end][c2]:
                                x_index1 = self.y[c1, t1]
                                x_index2 = self.y[c2, t2]
                                x_index = []
                                x_index.extend(x_index1)
                                x_index.extend(x_index2)
                                if is_hard:
                                    # 这两个课程不能同时被选中
                                    if self.hard_constraints_cache.get(f"y_{c1}_{t1}_{c2}_{t2}_1", False) == True: continue
                                    else: self.hard_constraints_cache[f"y_{c1}_{t1}_{c2}_{t2}_1"] = True
                                    self.hard_constraints[f"WorkDay_{c1}_{t1}_{c2}_{t2}"] = (x_index, 1)
                                else:
                                    self.soft_constraints[f"WorkDay_{c1}_{t1}_{c2}_{t2}"] = (x_index, 1, penalty)

    def _add_min_gap_constraint(self, classes, min_gap, is_hard, penalty):
        """
        MinGap(G): 两个课程之间必须有至少G个时间槽的间隙
        """
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            time_opts1 = self.class_to_time_options[c1]
            time_opts2 = self.class_to_time_options[c2]
            
            for topt1, tidx1 in time_opts1:
                if self.y.get((c1, tidx1), None) == None:
                    continue
                bits1 = topt1['optional_time_bits']
                weeks1, days1, start1, length1 = bits1
                end1 = start1 + length1
                
                for topt2, tidx2 in time_opts2:
                    if self.y.get((c2, tidx2), None) == None:
                        continue
                    bits2 = topt2['optional_time_bits']
                    weeks2, days2, start2, length2 = bits2
                    end2 = start2 + length2
                    
                    # 检查是否在同一week和day
                    weeks_int1 = int(weeks1, 2)
                    weeks_int2 = int(weeks2, 2)
                    days_int1 = int(days1, 2)
                    days_int2 = int(days2, 2)
                    
                    has_common_time = ((weeks_int1 & weeks_int2) != 0 and 
                                    (days_int1 & days_int2) != 0)
                    
                    if not has_common_time:
                        continue
                    
                    # 计算实际间隙
                    if start2 >= end1:
                        gap = start2 - end1
                    elif start1 >= end2:
                        gap = start1 - end2
                    else:
                        gap = -1  # 重叠
                    
                    # 如果间隙小于最小要求，则冲突
                    if gap < min_gap:
                        x_index1 = self.y[c1, tidx1]
                        x_index2 = self.y[c2, tidx2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"y_{c1}_{tidx1}_{c2}_{tidx2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"y_{c1}_{tidx1}_{c2}_{tidx2}_1"] = True
                            self.hard_constraints[f"MinGap_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"MinGap_{c1}_{tidx1}_{c2}_{tidx2}"] = (x_index, 1, penalty)

    #######################################################################################################
    # Constraints: (Pair-wise) Room
    #######################################################################################################

    def _add_same_room_constraint(self, classes, is_hard, penalty):
        """SameRoom: 课程必须在同一教室"""
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            # 对每个教室，要么都选，要么都不选
            rooms1 = self.class_to_room_options[c1]
            rooms2 = self.class_to_room_options[c2]
            
            for r1 in rooms1:
                if self.w.get((c1, r1), None) == None:
                    continue
                for r2 in rooms2:
                    if self.w.get((c2, r2), None) == None:
                        continue
                    if r1 != r2:
                        x_index1 = self.w[c1, r1]
                        x_index2 = self.w[c2, r2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"w_{c1}_{r1}_{c2}_{r2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"w_{c1}_{r1}_{c2}_{r2}_1"] = True
                            self.hard_constraints[f"SameRoom_{c1}_{r1}_{c2}_{r2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"SameRoom_{c1}_{r1}_{c2}_{r2}"] = (x_index, 1, penalty)
    
    def _add_different_room_constraint(self, classes, is_hard, penalty):
        """DifferentRoom: 课程必须在不同教室"""
        if len(classes) < 2:
            return
        
        for c1, c2 in combinations(classes, 2):
            if c1 not in self.reader.classes or c2 not in self.reader.classes:
                continue
            
            # 对每个教室，要么都选，要么都不选
            rooms1 = self.class_to_room_options[c1]
            rooms2 = self.class_to_room_options[c2]
            
            for r1 in rooms1:
                if self.w.get((c1, r1), None) == None:
                    continue
                for r2 in rooms2:
                    if self.w.get((c2, r2), None) == None:
                        continue
                    if r1 == r2:
                        x_index1 = self.w[c1, r1]
                        x_index2 = self.w[c2, r2]
                        x_index = []
                        x_index.extend(x_index1)
                        x_index.extend(x_index2)
                        if is_hard:
                            if self.hard_constraints_cache.get(f"w_{c1}_{r1}_{c2}_{r2}_1", False) == True: continue
                            else: self.hard_constraints_cache[f"w_{c1}_{r1}_{c2}_{r2}_1"] = True
                            self.hard_constraints[f"DifferentRoom_{c1}_{r1}_{c2}_{r2}"] = (x_index, 1)
                        else:
                            self.soft_constraints[f"DifferentRoom_{c1}_{r1}_{c2}_{r2}"] = (x_index, 1, penalty)

    #######################################################################################################
    # Constraints(After Assign): (Polygon) 
    #######################################################################################################

    # Day wise
    def _add_max_days_constraint(self, classes, max_days, is_hard, penalty, afterAssign):
        """MaxDays: 课程最多使用max_days天"""
        # TODO
        if afterAssign:
            if is_hard:
                print("This MaxDays Hard Constraint will be considered after assignment")
            else:
                print("This MaxDays Soft Constraint will be considered after assignment")
            return
        else:
            # TODO
            pass
            # print("Before Max Days hard_constraints: ", len(self.hard_constraints), " soft_constraints: ", len(self.soft_constraints))
            # if len(classes) == 0:
            #     return
            # day_ints_map = {}
            # for cid in classes:
            #     time_opts = self.class_to_time_options[cid]
            #     day_ints_map[cid] = []
            #     for topt, tidx in time_opts:
            #         if self.y.get((cid, tidx), None) == None:
            #             continue
            #         days_bits = topt['optional_time_bits'][1]
            #         work_days = days_bits.count("1")
            #         if work_days > max_days:
            #             x_index = self.y[cid, tidx]
            #             if is_hard:
            #                 self.hard_constraints[f"MaxDays_{cid}_{tidx}"] = (x_index, 0)
            #             else:
            #                 self.soft_constraints[f"MaxDays_{cid}_{tidx}"] = (x_index, 0, penalty * work_days - max_days)
            #             continue
            #         day_ints = int(days_bits, 2)
            #         day_ints_map[cid].append((cid, tidx, day_ints))
            #     # print("Max Days cid actions: ", len(day_ints_map[cid]))
            # Combinations = product(*day_ints_map.values())
            # # print("Max Days Combinations: ", len(list(Combinations)))
            # for Combination in Combinations:
            #     c_name = "MaxDays"
            #     x_index = []
            #     days_all_ints = 0
            #     count = 0
            #     for day_info in Combination:
            #         cid, tidx, _ = day_info
            #         c_name += f"_{cid}_{tidx}"
            #         x_index.extend(self.y[cid, tidx])
            #         day_ints = day_info[2]
            #         days_all_ints = days_all_ints | day_ints
            #         days_all = bin(days_all_ints)[2:]
            #         work_days = days_all.count("1")
            #         count += 1
            #         if work_days > max_days:
            #             if is_hard:
            #                 self.hard_constraints[c_name] = (x_index, count - 1)
            #                 break
            #             else:
            #                 self.soft_constraints[c_name] = (x_index, count - 1, penalty * work_days - max_days)
            # print("After Max Days hard_constraints: ", len(self.hard_constraints), " soft_constraints: ", len(self.soft_constraints))

    # Slot wise
    def _add_max_day_load_constraint(self, classes, max_slots, is_hard, penalty, afterAssign):
        """MaxDayLoad: 每天最多max_slots个时间槽"""
        if afterAssign:
            if is_hard:
                print("This MaxDayLoad Hard Constraint will be considered after assignment")
            else:
                print("This MaxDayLoad Soft Constraint will be considered after assignment")
            return
        else:
            # TODO
            pass
    
    # Slot wise
    def _add_max_breaks_constraint(self, classes, max_breaks, min_break_length, is_hard, penalty, afterAssign):
        """
        MaxBreaks(R,S): 限制课程间休息的次数
        R: 最大休息次数  
        S: 大于S个时间槽的间隙才算作休息
        
        核心思路：breaks数 = (合并后的块数) - 1
        其中合并时，gap ≤ S 的课程在同一块
        """
        if afterAssign:
            if is_hard:
                print("This MaxBreaks Hard Constraint will be considered after assignment")
            else:
                print("This MaxBreaks Soft Constraint will be considered after assignment")
            return
        else:
            # TODO
            pass
    
    # Slot wise
    def _add_max_block_constraint(self, classes, max_block_length, max_gap_in_block, is_hard, penalty, afterAssign):
        """
        MaxBlock(M,S): 限制连续课程块的长度
        M: 块的最大长度（时间槽）
        S: 小于S个时间槽的间隙仍被视为在同一块中
        
        一个"块"是一组课程，它们之间的间隙都小于S
        """
        if afterAssign:
            if is_hard:
                print("This MaxBlock Hard Constraint will be considered after assignment")
            else:
                print("This MaxBlock Soft Constraint will be considered after assignment")
            return
        else:
            # TODO
            pass

    #######################################################################################################
    # Latent Constraints(Optional: After Assign): (Pair-wise) Room 
    #######################################################################################################

    def _add_room_capacity_constraints(self, afterAssign=False):
        """添加教室容量约束（防止双重预订）"""
        print("Adding room capacity...")
        if afterAssign:
            print("This RoomCapacity Hard Constraint will be considered after assignment")
        else:
            # 对每个真实教室
            for rid in tqdm(self.reader.rooms.keys()):
                # 找到所有可能使用该教室的课程
                classes_using_room = []
                for cid, rooms in self.class_to_room_options.items():
                    if rid in rooms:
                        classes_using_room.append(cid)
                
                if len(classes_using_room) < 2:
                    continue
                
                # 对每对可能使用同一教室的课程，检查时间冲突
                for i, c1 in enumerate(classes_using_room):
                    for c2 in classes_using_room[i+1:]:
                        # 获取两个课程的所有时间选项
                        time_opts1 = self.class_to_time_options[c1]
                        time_opts2 = self.class_to_time_options[c2]
                        
                        # 检查所有时间选项对是否有冲突
                        for topt1, tidx1 in time_opts1:
                            if self.x.get((c1, tidx1, rid), None) == None:
                                continue
                        # for tidx1, topt1, tidx1, valid1 in options1:
                            if not self.class_to_valid_options[c1, tidx1, rid]:
                                continue
                            bits1 = topt1['optional_time_bits']
                            
                            for topt2, tidx2 in time_opts2:
                                if self.x.get((c2, tidx2, rid), None) == None:
                                    continue
                                if not self.class_to_valid_options[c2, tidx2, rid]:
                                    continue
                                bits2 = topt2['optional_time_bits']
                                mat2 = topt2['optional_time']
                                
                                # 使用位运算快速检查时间冲突
                                if self._times_conflict(bits1, bits2):
                                    x_index = []
                                    x_index.append(self.x[c1, tidx1, rid])
                                    x_index.append(self.x[c2, tidx2, rid])
                                    # 如果两个课程的这两个时间选项冲突，
                                    # 则不能同时在这个教室使用
                                    if (c1, tidx1, rid) in self.x and (c2, tidx2, rid) in self.x:
                                        if self.hard_constraints_cache.get(f"x_{c1}_{tidx1}_{rid}_{c2}_{tidx2}_{rid}_1", False) == True: continue
                                        else: self.hard_constraints_cache[f"x_{c1}_{tidx1}_{rid}_{c2}_{tidx2}_{rid}_1"] = True
                                        self.hard_constraints[f"SameRoomCrash_{c1}_{tidx1}_{rid}_{c2}_{tidx2}_{rid}"] = (x_index, 1)

    #######################################################################################################
    # Tools
    #######################################################################################################

    def build_hard_dist(self):
        num_c = len(self.hard_constraints)
        num_x = self.x_tensor.numel()

        # 初始化存储非零元素的索引和值
        indices = []  # 存储(i, x_index)的索引对
        values = []   # 存储非零值（都是1）
        upper = torch.empty(num_c, device=self.x_tensor.device)

        for i, (key, (x_index, u)) in enumerate(self.hard_constraints.items()):
            for idx in x_index:
                indices.append([i, idx])
                values.append(1.0)  # 非零值固定为1
            upper[i] = u

        # 将索引转换为COO格式要求的2维张量（shape: [2, nnz]）
        if indices:  # 避免空列表报错
            indices_tensor = torch.tensor(indices, dtype=torch.long).t().contiguous()
            values_tensor = torch.tensor(values, dtype=torch.float32, device=self.x_tensor.device)
            # 创建稀疏张量（COO格式）
            dist = torch.sparse_coo_tensor(
                indices=indices_tensor,
                values=values_tensor,
                size=(num_c, num_x),
                device=self.x_tensor.device,
                requires_grad=False  # 根据你的需求调整，若需反向传播则设为True
            )
        else:
            # 无约束时创建空的稀疏张量
            dist = torch.sparse_coo_tensor(
                torch.empty((2, 0), dtype=torch.long),
                torch.empty(0, dtype=torch.float32, device=self.x_tensor.device),
                size=(num_c, num_x),
                device=self.x_tensor.device
            )

        return dist, upper

    # def build_hard_dist(self):
    #     num_c = len(self.hard_constraints)
    #     num_x = self.x_tensor.numel()

    #     dist = torch.zeros((num_c, num_x), device=self.x_tensor.device)
    #     upper = torch.empty(num_c, device=self.x_tensor.device)

    #     for i, (_, (x_index, u)) in enumerate(self.hard_constraints.items()):
    #         dist[i, x_index] = 1
    #         upper[i] = u

    #     return dist, upper

    def build_soft_dist(self):
        num_c = len(self.soft_constraints)
        num_x = self.x_tensor.numel()

        # 初始化存储非零元素的索引和值
        indices = []  # 存储(i, x_index)的索引对
        values = []   # 存储非零值（都是1）
        upper = torch.empty(num_c, device=self.x_tensor.device)
        cost = torch.empty(num_c, device=self.x_tensor.device)

        for i, (key, (x_index, u, penalty)) in enumerate(self.soft_constraints.items()):
            for idx in x_index:
                indices.append([i, idx])
                values.append(1.0)  # 非零值固定为1
            upper[i] = u
            cost[i] = penalty

        # 将索引转换为COO格式要求的2维张量（shape: [2, nnz]）
        if indices:  # 避免空列表报错
            indices_tensor = torch.tensor(indices, dtype=torch.long).t().contiguous()
            values_tensor = torch.tensor(values, dtype=torch.float32, device=self.x_tensor.device)
            # 创建稀疏张量（COO格式）
            dist = torch.sparse_coo_tensor(
                indices=indices_tensor,
                values=values_tensor,
                size=(num_c, num_x),
                device=self.x_tensor.device,
                requires_grad=False  # 根据你的需求调整，若需反向传播则设为True
            )
        else:
            # 无约束时创建空的稀疏张量
            dist = torch.sparse_coo_tensor(
                torch.empty((2, 0), dtype=torch.long),
                torch.empty(0, dtype=torch.float32, device=self.x_tensor.device),
                size=(num_c, num_x),
                device=self.x_tensor.device
            )

        return dist, upper, cost

    # def build_soft_dist(self):
    #     num_c = len(self.soft_constraints)
    #     num_x = self.x_tensor.numel()

    #     dist = torch.zeros((num_c, num_x), device=self.x_tensor.device)
    #     upper = torch.empty(num_c, device=self.x_tensor.device)
    #     cost = torch.empty(num_c, device=self.x_tensor.device)

    #     for i, (_, (x_index, u, penalty)) in enumerate(self.soft_constraints.items()):
    #         dist[i, x_index] = 1
    #         upper[i] = u
    #         cost[i] = penalty

    #     return dist, upper, cost

    def _is_room_available(self, room_id, time_mat=None, time_bits=None):
        """
        检查教室在给定时间是否可用
        
        Args:
            room_id: 教室ID
            time_bits: (weeks_bits, days_bits, start, length)
        
        Returns:
            bool: True if 教室可用
        """
        if room_id not in self.reader.rooms:
            return True
        
        room_data = self.reader.rooms[room_id]
        unavailables = room_data.get('unavailables_bits', [])
        unavailable_zip = room_data.get('unavailable_zip', None)
        
        if not unavailables:
            return True
        
        if time_bits == None:
            if self._time_matrix_overlap(unavailable_zip, time_mat):
                return False
            return True
        
        else:
            # 检查是否与任何不可用时间冲突
            for unavail_bits in unavailables:
                unavail_weeks, unavail_days, unavail_start, unavail_length = unavail_bits
                
                if unavail_weeks is None or unavail_days is None:
                    continue
                if unavail_start is None or unavail_length is None:
                    continue
                
                if self._time_conflicts_with_unavailable(time_bits, unavail_bits):
                    return False
            
            return True

    def _time_matrix_overlap(self, time_matrix1, time_matrix2):
        overlap = torch.logical_and(time_matrix1, time_matrix2)
        return torch.any(overlap).item()

    def _times_conflict(self, time_bits1, time_bits2):
        """
        使用位运算快速检查两个时间是否冲突，带缓存
        """
        # 创建缓存键（确保顺序一致）
        if time_bits1 < time_bits2:
            cache_key = (time_bits1, time_bits2)
        else:
            cache_key = (time_bits2, time_bits1)
        
        # 检查缓存
        if cache_key in self.time_conflict_cache:
            return self.time_conflict_cache[cache_key]
        
        week_bits1, day_bits1, start1, length1 = time_bits1
        week_bits2, day_bits2, start2, length2 = time_bits2
        
        end1 = start1 + length1
        end2 = start2 + length2
        
        # 检查时间段是否重叠
        if not ((start1 < end2) and (start2 < end1)):
            self.time_conflict_cache[cache_key] = False
            return False
        
        # 使用位运算检查days是否有交集
        days_int1 = int(day_bits1, 2)
        days_int2 = int(day_bits2, 2)
        and_days = days_int1 & days_int2
        
        if and_days == 0:
            self.time_conflict_cache[cache_key] = False
            return False
        
        # 使用位运算检查weeks是否有交集
        week_int1 = int(week_bits1, 2)
        week_int2 = int(week_bits2, 2)
        and_week = week_int1 & week_int2
        
        if and_week == 0:
            self.time_conflict_cache[cache_key] = False
            return False
        
        self.time_conflict_cache[cache_key] = True
        return True

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
