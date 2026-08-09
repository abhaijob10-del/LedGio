from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("expenses", "0008_profile_picture_goal_name_deadline"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(
                fields=["user", "category"],
                name="expenses_tr_user_id_category_idx",
            ),
        ),
    ]
