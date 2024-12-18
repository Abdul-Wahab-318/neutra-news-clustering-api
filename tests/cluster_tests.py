# def test_no_articles_in_last_24_hours(mocker):
#     # Mock fetch_articles_last_24_hours to return an empty list
#     mocker.patch("your_module.fetch_articles_last_24_hours", return_value=[])
    
#     result = cluster_articles_test()
    
#     assert result["status"] == "success"
#     assert result["message"] == "No articles to cluster in the past 24hours"
#     assert result["result"] is None


# def test_single_article_blindspot(mocker):
#     mocker.patch("your_module.fetch_articles_last_24_hours", return_value=[
#         {"_id": "1", "title": "Single Article", "story_id": None, "scraped_date": "2024-12-17T10:00:00"}
#     ])
#     mocker.patch("your_module.get_cluster_pipeline", return_value=MockPipeline([-1]))
#     mocker.patch("your_module.insert_story", return_value="new_story_id")
#     mocker.patch("your_module.update_article", return_value=None)
    
#     result = cluster_articles_test()
    
#     assert result["status"] == "success"
#     # Verify insert_story and update_article are called
#     your_module.insert_story.assert_called_once_with("Single Article", "2024-12-17T10:00:00", blindspot=True)
#     your_module.update_article.assert_called_once_with("1", "new_story_id", blindspot=True)


# def test_multiple_articles_no_existing_stories(mocker):
#     articles = [
#         {"_id": "1", "title": "Article A", "story_id": None, "scraped_date": "2024-12-17T10:00:00"},
#         {"_id": "2", "title": "Article B", "story_id": None, "scraped_date": "2024-12-17T11:00:00"}
#     ]
#     mocker.patch("your_module.fetch_articles_last_24_hours", return_value=articles)
#     mocker.patch("your_module.get_cluster_pipeline", return_value=MockPipeline([0, 0]))
#     mocker.patch("your_module.insert_story", return_value="new_story_id")
#     mocker.patch("your_module.assign_story_id_to_articles", return_value=None)
    
#     result = cluster_articles_test()
    
#     assert result["status"] == "success"
#     # Verify insert_story is called once for the cluster
#     your_module.insert_story.assert_called_once_with("Article A", "2024-12-17T10:00:00", False)
#     your_module.assign_story_id_to_articles.assert_called_once_with(["1", "2"], "new_story_id", False)


# def test_articles_belonging_to_existing_stories(mocker):
#     articles = [
#         {"_id": "1", "title": "Article A", "story_id": "existing_story_id", "blindspot": False},
#         {"_id": "2", "title": "Article B", "story_id": None}
#     ]
#     mocker.patch("your_module.fetch_articles_last_24_hours", return_value=articles)
#     mocker.patch("your_module.get_cluster_pipeline", return_value=MockPipeline([0, 0]))
#     mocker.patch("your_module.assign_story_id_to_articles", return_value=None)
    
#     result = cluster_articles_test()
    
#     assert result["status"] == "success"
#     # Verify new articles are added to the existing story
#     your_module.assign_story_id_to_articles.assert_called_once_with(["2"], "existing_story_id", False)


# def test_blindspot_conversion(mocker):
#     articles = [
#         {"_id": "1", "title": "Article A", "story_id": "existing_story_id", "blindspot": True},
#         {"_id": "2", "title": "Article B", "story_id": None}
#     ]
#     mocker.patch("your_module.fetch_articles_last_24_hours", return_value=articles)
#     mocker.patch("your_module.get_cluster_pipeline", return_value=MockPipeline([0, 0]))
#     mocker.patch("your_module.update_story_blindspot_status", return_value=None)
#     mocker.patch("your_module.assign_story_id_to_articles", return_value=None)
    
#     result = cluster_articles_test()
    
#     assert result["status"] == "success"
#     # Verify blindspot status is updated
#     your_module.update_story_blindspot_status.assert_called_once_with("existing_story_id", False)
#     your_module.assign_story_id_to_articles.assert_called_once_with(["2"], "existing_story_id", False)


# def test_mixed_scenarios(mocker):
#     articles = [
#         {"_id": "1", "title": "Article A", "story_id": None},
#         {"_id": "2", "title": "Article B", "story_id": "existing_story_id", "blindspot": False},
#         {"_id": "3", "title": "Article C", "story_id": None}
#     ]
#     mocker.patch("your_module.fetch_articles_last_24_hours", return_value=articles)
#     mocker.patch("your_module.get_cluster_pipeline", return_value=MockPipeline([-1, 0, 0]))
#     mocker.patch("your_module.insert_story", return_value="new_story_id")
#     mocker.patch("your_module.update_article", return_value=None)
#     mocker.patch("your_module.assign_story_id_to_articles", return_value=None)
    
#     result = cluster_articles_test()
    
#     assert result["status"] == "success"
#     # Verify blindspot and new cluster handling
#     your_module.insert_story.assert_called_once_with("Article A", mocker.ANY, True)
#     your_module.update_article.assert_called_once_with("1", "new_story_id", True)
#     your_module.assign_story_id_to_articles.assert_called_once_with(["3"], "existing_story_id", False)
