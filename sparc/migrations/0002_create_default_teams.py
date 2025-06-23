from django.db import migrations

def create_default_teams(apps, schema_editor):
    Team = apps.get_model('sparc', 'Team')
    default_teams = [
        {'name': 'fiery_achievers', 'display_name': 'Fiery Achievers'},
        {'name': 'blazing_sparcs', 'display_name': 'Blazing SPARCS'},
        {'name': 'feisty_heroine', 'display_name': 'Feisty Heroine'},
        {'name': 'shining_phoeninx', 'display_name': 'Shining Phoeninx'},
        {'name': 'flameborn_champions', 'display_name': 'Flameborn Champions'},
    ]
    for team_data in default_teams:
        Team.objects.create(**team_data)

def reverse_default_teams(apps, schema_editor):
    Team = apps.get_model('sparc', 'Team')
    Team.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('sparc', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_teams, reverse_default_teams),
    ] 