"""种子数据：初始化演示数据"""
from .database import SessionLocal, Base, engine
from . import models

# 常见业态
CATEGORIES = ["餐饮", "便利店", "加油", "充电", "维修", "住宿", "卫生间"]


def seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 用户
        u1 = models.User(nickname="自驾老王", phone="13800000001")
        u2 = models.User(nickname="电车小妹", phone="13800000002")
        u3 = models.User(nickname="卡车司机", phone="13800000003")
        db.add_all([u1, u2, u3])
        db.flush()

        # 服务区
        area1 = models.ServiceArea(
            name="沪宁高速阳澄湖服务区",
            highway="G2京沪高速",
            mile_marker="K1180",
            latitude=31.42,
            longitude=120.72,
            description="以阳澄湖大闸蟹闻名的网红服务区，业态丰富。",
        )
        area2 = models.ServiceArea(
            name="京港澳高速窦店服务区",
            highway="G4京港澳高速",
            mile_marker="K37",
            latitude=39.67,
            longitude=116.08,
            description="华北地区大型综合服务区，加油充电便利。",
        )
        db.add_all([area1, area2])
        db.flush()

        # 商户 - 阳澄湖
        m1 = models.Merchant(
            service_area_id=area1.id, name="阳澄湖蟹味馆",
            category="餐饮", avg_price=88, open_hours="06:00-22:00",
            description="正宗阳澄湖大闸蟹，招牌蟹黄豆腐。",
        )
        m2 = models.Merchant(
            service_area_id=area1.id, name="老字号面馆",
            category="餐饮", avg_price=32, open_hours="24小时",
            description="苏州特色奥灶面，快速出餐。",
        )
        m3 = models.Merchant(
            service_area_id=area1.id, name="中石化加油站",
            category="加油", avg_price=None, open_hours="24小时",
            description="92/95/98号汽油及柴油。",
        )
        m4 = models.Merchant(
            service_area_id=area1.id, name="特来电快充站",
            category="充电", avg_price=None, open_hours="24小时",
            description="8 个 120kW 快充桩。",
        )
        # 商户 - 窦店
        m5 = models.Merchant(
            service_area_id=area2.id, name="庆丰包子铺",
            category="餐饮", avg_price=25, open_hours="06:00-21:00",
            description="经典北京小吃，猪肉大葱包子。",
        )
        m6 = models.Merchant(
            service_area_id=area2.id, name="国网充电站",
            category="充电", avg_price=None, open_hours="24小时",
            description="16 个 60kW 直流快充桩。",
        )
        db.add_all([m1, m2, m3, m4, m5, m6])
        db.flush()

        # 点评（部分已审核）
        reviews = [
            models.Review(merchant_id=m1.id, user_id=u1.id, rating=5,
                          content="大闸蟹新鲜，环境干净，就是节假日人有点多。",
                          tags="干净,味道好", is_approved=True),
            models.Review(merchant_id=m1.id, user_id=u2.id, rating=4,
                          content="价格偏贵但值得一尝，蟹黄很足。",
                          tags="价格偏贵", is_approved=True),
            models.Review(merchant_id=m2.id, user_id=u1.id, rating=5,
                          content="奥灶面汤头一绝，24小时营业太贴心了。",
                          tags="味道好,24小时", is_approved=True),
            models.Review(merchant_id=m4.id, user_id=u2.id, rating=4,
                          content="充电速度快，但高峰期要排队。",
                          tags="速度快,排队久", is_approved=True),
            models.Review(merchant_id=m5.id, user_id=u3.id, rating=5,
                          content="包子馅大皮薄，性价比高。",
                          tags="干净,性价比高", is_approved=True),
            # 一条待审核
            models.Review(merchant_id=m3.id, user_id=u3.id, rating=3,
                          content="加油站设备略旧，自助加油不方便。",
                          tags="设备旧", is_approved=False),
        ]
        db.add_all(reviews)
        db.commit()

        # 重算评分
        from .crud import _recompute_merchant_rating
        for m in [m1, m2, m4, m5]:
            _recompute_merchant_rating(db, m.id)

        print("种子数据写入完成。")
        print(f"  服务区: {len(db.query(models.ServiceArea).all())} 个")
        print(f"  商户: {len(db.query(models.Merchant).all())} 个")
        print(f"  点评: {len(db.query(models.Review).all())} 条")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
