# Runtime Optimization (Module 1 + 2)

## Toi uu tai nguyen

- Uu tien fp16/bf16 neu GPU ho tro.
- Chay caption theo batch nho (thap nhat la 1).
- Giai phong model sau moi stage nang.
- Goi `torch.cuda.empty_cache()` truoc khi doi model.

## Toi uu toc do

- Cache output trung gian: `audio_16k.wav`, keyframes, metadata.
- Co co che resume (bo qua buoc da tao output hop le).
- Giam keyframe bang tuning scene detect truoc khi caption.

## Logging nen luu

- Tong so keyframes.
- Tong so transcript segments.
- Thoi gian chay tung stage.
- Cau hinh da dung: threshold, min_scene_len, image_size, model_name.
