from src.utils.dataReader import PSTTReader
from src.utils.ConstraintsResolver_v2 import ConstraintsResolver
import pathlib
import torch

folder = pathlib.Path(__file__).parent.resolve()

def check_gpu_memory():
    """查看PyTorch环境下GPU显存占用"""
    # 检查是否有可用GPU
    if torch.cuda.is_available():
        # 遍历所有GPU
        for i in range(torch.cuda.device_count()):
            print(f"\n=== GPU {i}: {torch.cuda.get_device_name(i)} ===")
            # 总显存（单位：MB）
            total_memory = torch.cuda.get_device_properties(i).total_memory / 1024 / 1024
            # 已用显存
            used_memory = torch.cuda.memory_allocated(i) / 1024 / 1024
            # 缓存显存（PyTorch预分配但未使用的显存）
            cached_memory = torch.cuda.memory_reserved(i) / 1024 / 1024
            
            print(f"总显存: {total_memory:.2f} MB")
            print(f"已用显存: {used_memory:.2f} MB")
            print(f"缓存显存: {cached_memory:.2f} MB")
            print(f"剩余显存: {total_memory - used_memory:.2f} MB")
            
            # 清空缓存（可选，释放未使用的缓存显存）
            torch.cuda.empty_cache()
    else:
        print("无可用GPU")

if __name__ == "__main__":
    file = f"{folder}/data/reduced/muni-fi-fal17.xml"
    reader = PSTTReader(file, matrix=True)
    constraints = ConstraintsResolver(reader, 'cuda:0')
    constraints.build_model()
    # 调用函数查看
    check_gpu_memory()